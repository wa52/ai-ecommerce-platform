const nextConfig = {
  // 本地开发常用 127.0.0.1 打开页面；允许 Next 的客户端开发资源正常加载。
  allowedDevOrigins: ["127.0.0.1"],
  // 让浏览器只访问商城同源地址；容器内部再转发到业务服务。
  // 这样临时公网演示只需暴露 3000，不会把 Saleor/FastAPI 直接暴露出去。
  async rewrites() {
    return [
      {
        source: "/graphql",
        destination: "http://saleor-api:8000/graphql/",
      },
      {
        source: "/graphql/",
        destination: "http://saleor-api:8000/graphql/",
      },
      {
        source: "/api/v1/:path*",
        destination: "http://ai-backend:8000/api/v1/:path*",
      },
      {
        source: "/media/:path*",
        destination: "http://saleor-api:8000/media/:path*",
      },
      {
        source: "/thumbnail/:path*",
        destination: "http://saleor-api:8000/thumbnail/:path*",
      },
    ];
  },
};

export default nextConfig;
