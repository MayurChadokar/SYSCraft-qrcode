from fastapi import APIRouter

router = APIRouter(prefix="/api/templates", tags=["Templates"])

CATALOG = [
    {"id":"business-card", "name":"Company Business Card", "qr_type":"vcard", "description":"Share a polished contact card."},
    {"id":"employee", "name":"Employee Contact", "qr_type":"vcard", "description":"Help colleagues connect instantly."},
    {"id":"product", "name":"Product QR", "qr_type":"product", "description":"Encode product details and SKU."},
    {"id":"website", "name":"Website QR", "qr_type":"url", "description":"Send scanners to your website."},
    {"id":"menu", "name":"Restaurant Menu", "qr_type":"url", "description":"Link guests to a digital menu."},
    {"id":"wifi", "name":"Wi-Fi Access", "qr_type":"wifi", "description":"Securely share network access."},
    {"id":"event", "name":"Event Registration", "qr_type":"event", "description":"Share an event invitation."},
    {"id":"support", "name":"Customer Support", "qr_type":"whatsapp", "description":"Open a support conversation."},
    {"id":"company", "name":"Company Profile", "qr_type":"company", "description":"Share company information."},
]

@router.get("")
def list_templates():
    return {"items": CATALOG}
