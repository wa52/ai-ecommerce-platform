# Storefront 一次性初始化（幂等）：商用前置设置
# 1) 关闭注册邮箱确认（沙箱环境没有真实 SMTP，Mailpit 仅本地收信）
# 2) 确保所有已发布商品在渠道 Listing 中可见（visibleInListings=True）
#
# 用法: powershell -File scripts\saleor_storefront_init.ps1
# 前置: docker compose 栈已启动

$ErrorActionPreference = "Stop"

$py1 = "from saleor.site.models import SiteSettings; SiteSettings.objects.update(enable_account_confirmation_by_email=False); print('email confirmation: disabled')"
$py2 = "from saleor.product.models import ProductChannelListing; changed = ProductChannelListing.objects.filter(is_published=True).exclude(visible_in_listings=True).update(visible_in_listings=True); print('channel listings updated:', changed)"

Write-Host "[1/2] 关闭 Saleor 注册邮箱确认（幂等）"
docker compose exec -T saleor-api python3 manage.py shell -c $py1
if ($LASTEXITCODE -ne 0) { throw "saleor-api manage.py shell 执行失败" }

Write-Host "[2/2] 补齐商品渠道 Listing 可见性（幂等）"
docker compose exec -T saleor-api python3 manage.py shell -c $py2
if ($LASTEXITCODE -ne 0) { throw "saleor-api manage.py shell 执行失败" }

Write-Host "完成。Storefront: http://localhost:3000"
Write-Host "管理员账号: docker compose exec -T saleor-api python3 manage.py createsuperuser --email admin@example.com"
