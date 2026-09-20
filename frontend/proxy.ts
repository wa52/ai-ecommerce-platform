import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * 同一份前端代码可以构建成两个独立部署单元：
 * - APP_ROLE=storefront：只提供消费者商城；
 * - APP_ROLE=admin：只提供商家后台。
 *
 * 这是服务端路由隔离，不依赖前端隐藏菜单。后台 API 仍由 FastAPI/Saleor
 * 的 Bearer token 权限做第二层校验。
 */
export function proxy(request: NextRequest) {
  const role = process.env.APP_ROLE ?? "all";
  const pathname = request.nextUrl.pathname;

  if (role === "storefront" && pathname.startsWith("/admin")) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  if (role === "admin" && !pathname.startsWith("/admin")) {
    return NextResponse.redirect(new URL("/admin", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
