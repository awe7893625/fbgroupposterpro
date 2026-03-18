import os

import aiohttp
from aiohttp import web

VERCEL_PROXY_URL = os.environ.get(
    "VERCEL_PROXY_URL", "https://fbgroupposter.vercel.app/api/ai-proxy"
)


def setup_routes(app, cors):
    r = cors.add(app.router.add_resource("/api/ai/generate"))
    cors.add(r.add_route("POST", generate_ai_content))


async def generate_ai_content(request):
    data = await request.json()
    product_data = data.get("product_data") or data.get("productData")
    style = data.get("style", "professional")
    variant_count = data.get("variant_count", 3)
    license_key = data.get("license_key") or data.get("licenseKey", "")
    device_id = data.get("device_id") or data.get("deviceId", "")

    if not product_data:
        raise web.HTTPBadRequest(reason="product_data required")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                VERCEL_PROXY_URL,
                json={
                    "productData": product_data,
                    "style": style,
                    "variantCount": variant_count,
                    "licenseKey": license_key,
                    "deviceId": device_id,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise web.HTTPBadGateway(reason=f"AI proxy error: {text[:200]}")
                result = await resp.json()
                return web.json_response(result)
        except aiohttp.ClientError as e:
            raise web.HTTPServiceUnavailable(reason=f"AI proxy unavailable: {str(e)}")
