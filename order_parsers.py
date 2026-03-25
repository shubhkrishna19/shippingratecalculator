from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Dict, List, Optional


PINCODE_RE = re.compile(r"\b(\d{6})\b")
PHONE_RE = re.compile(r"\b(\d{10})\b")


@dataclass
class ParsedUpload:
    parser_key: str
    source_platform: str
    rows: List[Dict[str, Any]]


def parse_upload(file_name: str, payload: bytes) -> ParsedUpload:
    text = payload.decode("utf-8-sig", errors="replace")
    parser_key = detect_parser(file_name, text)

    if parser_key == "amazon_all_orders":
        return ParsedUpload(parser_key, "Amazon", _parse_amazon_all_orders(file_name, text))
    if parser_key == "amazon_self_ship":
        return ParsedUpload(parser_key, "Amazon", _parse_amazon_self_ship(file_name, text))
    if parser_key == "flipkart_self_ship":
        return ParsedUpload(parser_key, "Flipkart", _parse_flipkart_self_ship(file_name, text))
    if parser_key == "flipkart_easy_ship":
        return ParsedUpload(parser_key, "Flipkart", _parse_flipkart_easy_ship(file_name, text))
    if parser_key == "pepperfry":
        return ParsedUpload(parser_key, "Pepperfry", _parse_pepperfry(file_name, text))
    if parser_key == "urban_ladder":
        return ParsedUpload(parser_key, "Urban Ladder", _parse_urban_ladder(file_name, text))

    raise ValueError(f"Unsupported order file format: {file_name}")


def detect_parser(file_name: str, text: str) -> str:
    lowered_name = file_name.lower()
    lines = [line for line in text.splitlines() if line.strip()]
    head = "\n".join(lines[:5])

    if "amazon-order-id\tmerchant-order-id" in head:
        return "amazon_all_orders"
    if "order-id\torder-item-id\tpurchase-date" in head:
        return "amazon_self_ship"
    if "Ordered On,Shipment ID,ORDER ITEM ID,Order Id" in head:
        return "flipkart_easy_ship"
    if "Ordered On,FSN,Product,HAS OFFER,Order Id" in head or "Delivery partner and logistics partner names are mandatory" in head:
        return "flipkart_self_ship"
    if "\"Order ID-SKU\",QTY" in head or "Order ID-SKU" in head:
        return "pepperfry"
    if "\"order_code\",\"item_code\",\"sku\"" in head or "order_code,item_code,sku" in head:
        return "urban_ladder"
    if lowered_name.endswith(".txt"):
        if "order-id\torder-item-id" in head:
            return "amazon_self_ship"
        return "amazon_all_orders"

    raise ValueError(f"Could not detect file format for {file_name}")


def _parse_amazon_all_orders(file_name: str, text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for row_number, raw in enumerate(reader, start=2):
        sku = _pick(raw, "sku")
        quantity = _int_or_default(_pick(raw, "quantity"), 1)
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Amazon",
                parser_key="amazon_all_orders",
                source_row_number=row_number,
                order_id=_pick(raw, "amazon-order-id"),
                order_item_id=_pick(raw, "merchant-order-id") or sku,
                sku=sku,
                quantity=quantity,
                product_name=_pick(raw, "product-name"),
                order_status=_pick(raw, "order-status") or _pick(raw, "item-status"),
                order_date=_pick(raw, "purchase-date"),
                customer_name=_pick(raw, "buyer-company-name"),
                ship_to_name=_pick(raw, "buyer-company-name"),
                city=_pick(raw, "ship-city"),
                state=_pick(raw, "ship-state"),
                pincode=_pick(raw, "ship-postal-code"),
                phone="",
                email="",
                address_line_1="",
                address_line_2="",
                address_line_3="",
                ship_service_level=_pick(raw, "ship-service-level"),
                item_value=_float_or_none(_pick(raw, "item-price")),
                currency=_pick(raw, "currency"),
                dispatch_by_date="",
                promised_delivery_date="",
                lookup_candidates=[sku, _pick(raw, "asin")],
                raw_fields={
                    "asin": _pick(raw, "asin"),
                    "sales_channel": _pick(raw, "sales-channel"),
                },
            )
        )
    return rows


def _parse_amazon_self_ship(file_name: str, text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    rows: list[dict[str, Any]] = []
    for row_number, raw in enumerate(reader, start=2):
        sku = _pick(raw, "sku")
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Amazon",
                parser_key="amazon_self_ship",
                source_row_number=row_number,
                order_id=_pick(raw, "order-id"),
                order_item_id=_pick(raw, "order-item-id"),
                sku=sku,
                quantity=_int_or_default(_pick(raw, "quantity-purchased"), 1),
                product_name=_pick(raw, "product-name"),
                order_status=_pick(raw, "shipment-status"),
                order_date=_pick(raw, "purchase-date"),
                customer_name=_pick(raw, "buyer-name"),
                ship_to_name=_pick(raw, "recipient-name"),
                city=_pick(raw, "ship-city"),
                state=_pick(raw, "ship-state"),
                pincode=_pick(raw, "ship-postal-code"),
                phone=_pick(raw, "buyer-phone-number"),
                email=_pick(raw, "buyer-email"),
                address_line_1=_pick(raw, "ship-address-1"),
                address_line_2=_pick(raw, "ship-address-2"),
                address_line_3=_pick(raw, "ship-address-3"),
                ship_service_level=_pick(raw, "ship-service-level"),
                item_value=None,
                currency="INR",
                dispatch_by_date=_pick(raw, "promise-date"),
                promised_delivery_date=_pick(raw, "promise-date"),
                lookup_candidates=[sku],
                raw_fields={"ship_service_name": _pick(raw, "ship-service-name")},
            )
        )
    return rows


def _parse_flipkart_self_ship(file_name: str, text: str) -> list[dict[str, Any]]:
    lines = [line for line in text.splitlines() if line.strip()]
    header_index = next(
        index for index, line in enumerate(lines) if line.startswith("Ordered On,FSN,Product")
    )
    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    rows: list[dict[str, Any]] = []

    for row_number, raw in enumerate(reader, start=header_index + 2):
        sku = _pick(raw, "SKU Code")
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Flipkart",
                parser_key="flipkart_self_ship",
                source_row_number=row_number,
                order_id=_pick(raw, "Order Id"),
                order_item_id=_pick(raw, "ORDER ITEM ID"),
                sku=sku,
                quantity=_int_or_default(_pick(raw, "Quantity"), 1),
                product_name=_pick(raw, "Product"),
                order_status=_pick(raw, "Order State"),
                order_date=_pick(raw, "Ordered On"),
                customer_name=_pick(raw, "Buyer name"),
                ship_to_name=_pick(raw, "Ship to name"),
                city=_pick(raw, "City"),
                state=_pick(raw, "State"),
                pincode=_pick(raw, "PIN Code"),
                phone=_pick(raw, "Phone No"),
                email=_pick(raw, "Email Id"),
                address_line_1=_pick(raw, "Address Line 1"),
                address_line_2=_pick(raw, "Address Line 2"),
                address_line_3="",
                ship_service_level="",
                item_value=_float_or_none(_pick(raw, "Total (includes FKMP contribution)")),
                currency="INR",
                dispatch_by_date=_pick(raw, "Dispatch By Date"),
                promised_delivery_date=_pick(raw, "Deliver By Date"),
                lookup_candidates=[sku, _pick(raw, "FSN")],
                raw_fields={"fsn": _pick(raw, "FSN")},
            )
        )
    return rows


def _parse_flipkart_easy_ship(file_name: str, text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for row_number, raw in enumerate(reader, start=2):
        sku = _pick(raw, "SKU")
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Flipkart",
                parser_key="flipkart_easy_ship",
                source_row_number=row_number,
                order_id=_pick(raw, "Order Id"),
                order_item_id=_pick(raw, "ORDER ITEM ID"),
                sku=sku,
                quantity=_int_or_default(_pick(raw, "Quantity"), 1),
                product_name=_pick(raw, "Product"),
                order_status=_pick(raw, "Order State"),
                order_date=_pick(raw, "Ordered On"),
                customer_name=_pick(raw, "Buyer name"),
                ship_to_name=_pick(raw, "Ship to name"),
                city=_pick(raw, "City"),
                state=_pick(raw, "State"),
                pincode=_pick(raw, "PIN Code"),
                phone="",
                email="",
                address_line_1=_pick(raw, "Address Line 1"),
                address_line_2=_pick(raw, "Address Line 2"),
                address_line_3="",
                ship_service_level="",
                item_value=_float_or_none(_pick(raw, "Price inc. FKMP Contribution & Subsidy")),
                currency="INR",
                dispatch_by_date=_pick(raw, "Dispatch by date"),
                promised_delivery_date="",
                lookup_candidates=[sku, _pick(raw, "FSN")],
                raw_fields={
                    "fsn": _pick(raw, "FSN"),
                    "package_weight_kg": _float_or_none(_pick(raw, "Package Weight (kg)")),
                },
            )
        )
    return rows


def _parse_pepperfry(file_name: str, text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []

    for row_number, raw in enumerate(reader, start=2):
        order_code = _pick(raw, "Order ID-SKU")
        parsed_address = _parse_pepperfry_address(_pick(raw, "Shipping Address"))
        your_sku = _pick(raw, "Your SKU ID")
        pf_sku = _pick(raw, "SKU ID")
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Pepperfry",
                parser_key="pepperfry",
                source_row_number=row_number,
                order_id=order_code.split("_")[0] if order_code else "",
                order_item_id=order_code,
                sku=your_sku or pf_sku,
                quantity=_int_or_default(_pick(raw, "QTY"), 1),
                product_name=_pick(raw, "Product Name"),
                order_status=_pick(raw, "status"),
                order_date=_pick(raw, "Order Confirmed Date"),
                customer_name=_pick(raw, "Customer Name"),
                ship_to_name=_pick(raw, "Customer Name"),
                city=parsed_address["city"],
                state=parsed_address["state"],
                pincode=parsed_address["pincode"],
                phone=parsed_address["phone"],
                email="",
                address_line_1=parsed_address["line_1"],
                address_line_2=parsed_address["line_2"],
                address_line_3=parsed_address["line_3"],
                ship_service_level="",
                item_value=_float_or_none(_pick(raw, "TOTAL")),
                currency="INR",
                dispatch_by_date=_pick(raw, "To be shippped Before"),
                promised_delivery_date=_pick(raw, "Promised Delivery Date"),
                lookup_candidates=[your_sku, pf_sku],
                raw_fields={"pepperfry_sku_id": pf_sku},
            )
        )
    return rows


def _parse_urban_ladder(file_name: str, text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []

    for row_number, raw in enumerate(reader, start=2):
        ul_sku = _pick(raw, "sku")
        rows.append(
            _base_row(
                source_file=file_name,
                source_platform="Urban Ladder",
                parser_key="urban_ladder",
                source_row_number=row_number,
                order_id=_pick(raw, "order_code"),
                order_item_id=_pick(raw, "item_code"),
                sku=ul_sku,
                quantity=1,
                product_name=_pick(raw, "item_description"),
                order_status=_pick(raw, "status"),
                order_date=_pick(raw, "order_placed_at"),
                customer_name=_pick(raw, "customer_name"),
                ship_to_name=_pick(raw, "customer_name"),
                city=_pick(raw, "ship_city"),
                state="",
                pincode=_pick(raw, "ship_pincode"),
                phone=_pick(raw, "customer_phone"),
                email="",
                address_line_1=_pick(raw, "ship_address_line1"),
                address_line_2=_pick(raw, "ship_address_line2"),
                address_line_3="",
                ship_service_level="",
                item_value=_float_or_none(_pick(raw, "item_value")),
                currency="INR",
                dispatch_by_date=_pick(raw, "item_pdd"),
                promised_delivery_date=_pick(raw, "item_pdd"),
                lookup_candidates=[ul_sku],
                raw_fields={},
            )
        )
    return rows


def _base_row(
    *,
    source_file: str,
    source_platform: str,
    parser_key: str,
    source_row_number: int,
    order_id: Optional[str],
    order_item_id: Optional[str],
    sku: Optional[str],
    quantity: int,
    product_name: Optional[str],
    order_status: Optional[str],
    order_date: Optional[str],
    customer_name: Optional[str],
    ship_to_name: Optional[str],
    city: Optional[str],
    state: Optional[str],
    pincode: Optional[str],
    phone: Optional[str],
    email: Optional[str],
    address_line_1: Optional[str],
    address_line_2: Optional[str],
    address_line_3: Optional[str],
    ship_service_level: Optional[str],
    item_value: Optional[float],
    currency: Optional[str],
    dispatch_by_date: Optional[str],
    promised_delivery_date: Optional[str],
    lookup_candidates: List[Optional[str]],
    raw_fields: dict[str, Any],
) -> dict[str, Any]:
    return {
        "source_file": source_file,
        "source_platform": source_platform,
        "parser_key": parser_key,
        "source_row_number": source_row_number,
        "order_id": order_id or "",
        "order_item_id": order_item_id or "",
        "sku": sku or "",
        "quantity": quantity,
        "product_name": product_name or "",
        "order_status": order_status or "",
        "order_date": order_date or "",
        "customer_name": customer_name or "",
        "ship_to_name": ship_to_name or "",
        "city": city or "",
        "state": state or "",
        "pincode": _digits_only(pincode),
        "phone": _digits_only(phone),
        "email": email or "",
        "address_line_1": address_line_1 or "",
        "address_line_2": address_line_2 or "",
        "address_line_3": address_line_3 or "",
        "ship_service_level": ship_service_level or "",
        "item_value": item_value,
        "currency": currency or "INR",
        "dispatch_by_date": dispatch_by_date or "",
        "promised_delivery_date": promised_delivery_date or "",
        "lookup_candidates": [candidate for candidate in lookup_candidates if candidate],
        "raw_fields": raw_fields,
    }


def _parse_pepperfry_address(raw_address: Optional[str]) -> dict[str, str]:
    if not raw_address:
        return {"line_1": "", "line_2": "", "line_3": "", "city": "", "state": "", "pincode": "", "phone": ""}

    cleaned = unescape(raw_address.replace("<br/>", "\n"))
    parts = [part.strip().replace("undefined", "").strip() for part in cleaned.splitlines() if part.strip()]
    joined = " ".join(parts)

    pincode_match = PINCODE_RE.search(joined)
    phone_match = PHONE_RE.search(joined)

    state = ""
    state_candidates = [part for part in parts if part.endswith(" IN")]
    if state_candidates:
        state = state_candidates[-1].replace(" IN", "").split()[-1]

    line_1 = parts[1] if len(parts) > 1 else ""
    line_2 = parts[2] if len(parts) > 2 else ""
    line_3 = parts[3] if len(parts) > 3 else ""

    return {
        "line_1": line_1,
        "line_2": line_2,
        "line_3": line_3,
        "city": "",
        "state": state,
        "pincode": pincode_match.group(1) if pincode_match else "",
        "phone": phone_match.group(1) if phone_match else "",
    }


def _pick(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    return str(value).strip() if value is not None else ""


def _digits_only(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _int_or_default(value: Optional[str], default: int) -> int:
    try:
        return int(float(value)) if value not in (None, "") else default
    except ValueError:
        return default


def _float_or_none(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None
