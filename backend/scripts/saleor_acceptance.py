import json
import os
import urllib.error
import urllib.request

API = os.environ.get("SALEOR_API_URL", "http://localhost:8000/graphql/")
SLUG = "phase1-acceptance-product"
EMAIL = os.environ["SALEOR_ADMIN_EMAIL"]
PASSWORD = os.environ["SALEOR_ADMIN_PASSWORD"]


def gql(query, variables=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


_, auth = gql(
    "mutation Login($email: String!, $password: String!) {"
    " tokenCreate(email: $email, password: $password) { token } }",
    {"email": EMAIL, "password": PASSWORD},
)
tok = auth["data"]["tokenCreate"]["token"]
print("login: OK")

_, pt_query = gql("{ productTypes(first: 1) { edges { node { id name } } } }", token=tok)
pt_id = pt_query["data"]["productTypes"]["edges"][0]["node"]["id"]

status, created = gql(
    """
    mutation CreateProduct($input: ProductCreateInput!) {
      productCreate(input: $input) { product { id name slug } errors { field message } }
    }
    """,
    {"input": {"name": "Phase 1 Acceptance Product", "slug": SLUG, "productType": pt_id}},
    token=tok,
)
pc = created["data"]["productCreate"]
if pc.get("product"):
    print("productCreate:", status, "created", json.dumps(pc["product"], ensure_ascii=False))
elif any("already exists" in e["message"] for e in pc.get("errors", [])):
    print("productCreate:", status, "already exists -> idempotent re-run")
else:
    raise SystemExit(f"create failed: {pc}")

status, rb = gql("{ products(first: 20) { edges { node { id name slug } } } }", token=tok)
nodes = [e["node"] for e in rb["data"]["products"]["edges"]]
node = next((n for n in nodes if n["slug"] == SLUG), None)
print("read-back:", json.dumps(node, ensure_ascii=False))
assert node and node["name"] == "Phase 1 Acceptance Product"
print("SALEOR WRITE+READ: PASS")
