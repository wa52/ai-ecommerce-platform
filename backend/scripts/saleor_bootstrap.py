"""Saleor 一次性引导：确保存在可创建 SKU 变体的 product type。

- 属性 SIZE（DROPDOWN）及取值 M
- product type（slug 由 SALEOR_DEFAULT_PRODUCT_TYPE_SLUG 指定）绑定 SIZE 为变体属性

幂等：重复执行不会产生重复数据。凭据从环境变量读取。
"""

import json
import os
import sys
import urllib.error
import urllib.request

SALEOR = os.environ.get("SALEOR_API_URL", "http://localhost:8000/graphql/")
EMAIL = os.environ["SALEOR_ADMIN_EMAIL"]
PASSWORD = os.environ["SALEOR_ADMIN_PASSWORD"]
TYPE_SLUG = os.environ.get("SALEOR_DEFAULT_PRODUCT_TYPE_SLUG", "default-type")
TYPE_NAME = os.environ.get("SALEOR_DEFAULT_PRODUCT_TYPE_NAME", "Default Type")
ATTRIBUTE_SLUG = os.environ.get("SALEOR_VARIANT_ATTRIBUTE_SLUG", "size")
ATTRIBUTE_NAME = os.environ.get("SALEOR_VARIANT_ATTRIBUTE_NAME", "Size")
ATTRIBUTE_VALUE = os.environ.get("SALEOR_VARIANT_ATTRIBUTE_VALUE", "M")


def gql(query: str, variables: dict | None = None, token: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        SALEOR,
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:600]}") from exc
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def errors_of(payload: dict) -> list[dict]:
    return payload.get("errors") or []


def main() -> int:
    token = gql(
        "mutation Login($e: String!, $p: String!) { tokenCreate(email: $e, password: $p) { token errors { message } } }",
        {"e": EMAIL, "p": PASSWORD},
    )["tokenCreate"]["token"]
    print("login: OK")

    # 1. 属性
    existing_attr = gql(
        """
        query A($slug: String!) {
          attribute(slug: $slug) { id name choices(first: 50) { edges { node { id slug } } } }
        }
        """,
        {"slug": ATTRIBUTE_SLUG},
        token,
    )["attribute"]
    if existing_attr:
        attribute_id = existing_attr["id"]
        choices = [e["node"] for e in existing_attr["choices"]["edges"]]
        has_value = any(c["slug"] == ATTRIBUTE_VALUE.lower() for c in choices)
        print(f"attribute exists: {ATTRIBUTE_SLUG} ({attribute_id})")
    else:
        created = gql(
            """
            mutation CreateAttr($input: AttributeCreateInput!) {
              attributeCreate(input: $input) { attribute { id name } errors { field message } }
            }
            """,
            {
                "input": {
                    "name": ATTRIBUTE_NAME,
                    "slug": ATTRIBUTE_SLUG,
                    "type": "PRODUCT_TYPE",
                    "inputType": "DROPDOWN",
                    "values": [{"name": ATTRIBUTE_VALUE}],
                }
            },
            token,
        )["attributeCreate"]
        if errors_of(created):
            print("attributeCreate errors:", created["errors"])
            return 1
        attribute_id = created["attribute"]["id"]
        has_value = True
        print(f"attribute created: {ATTRIBUTE_SLUG} ({attribute_id})")

    if not has_value:
        value_created = gql(
            f"""
            mutation CreateValue($input: AttributeValueCreateInput!) {{
              attributeValueCreate(attribute: "{attribute_id}", input: $input) {{
                attributeValue {{ id name }} errors {{ field message }}
              }}
            }}
            """,
            {"input": {"name": ATTRIBUTE_VALUE}},
            token,
        )["attributeValueCreate"]
        if errors_of(value_created):
            print("attributeValueCreate errors:", value_created["errors"])
            return 1
        print(f"attribute value created: {ATTRIBUTE_VALUE}")

    # 2. product type
    existing_type = gql(
        """
        query T($slug: String!) {
          productTypes(first: 1, filter: {slugs: [$slug]}) {
            edges { node { id name variantAttributes { id slug } } }
          }
        }
        """,
        {"slug": TYPE_SLUG},
        token,
    )["productTypes"]["edges"]
    existing_type = existing_type[0]["node"] if existing_type else None
    if existing_type:
        type_id = existing_type["id"]
        print(f"product type exists: {TYPE_SLUG} ({type_id})")
    else:
        created_type = gql(
            """
            mutation CreateType($input: ProductTypeInput!) {
              productTypeCreate(input: $input) { productType { id name } errors { field message } }
            }
            """,
            {"input": {"name": TYPE_NAME, "slug": TYPE_SLUG, "hasVariants": True}},
            token,
        )["productTypeCreate"]
        if errors_of(created_type):
            print("productTypeCreate errors:", created_type["errors"])
            return 1
        type_id = created_type["productType"]["id"]
        print(f"product type created: {TYPE_SLUG} ({type_id})")

    # 3. 绑定变体属性
    bound = gql(
        """
        mutation BindAttr($id: ID!, $input: ProductTypeInput!) {
          productTypeUpdate(id: $id, input: $input) { productType { id variantAttributes { slug } } errors { field message } }
        }
        """,
        {"id": type_id, "input": {"variantAttributes": [attribute_id], "hasVariants": True}},
        token,
    )["productTypeUpdate"]
    if errors_of(bound):
        print("productTypeUpdate errors:", bound["errors"])
        return 1
    print("variant attributes bound:", [a["slug"] for a in bound["productType"]["variantAttributes"]])
    print("BOOTSTRAP: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
