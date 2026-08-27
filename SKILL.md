---
name: lingxi-task-center-checkin
description: WPS 灵犀（灵犀专业版 / lingxi.kdocs.cn Web端）任务中心每日签到自动化技能。通过已登录灵犀账号的浏览器（推荐 Edge）打开灵犀 Web 端，在页面内调用官方签到接口完成「每日签到」并领取 200 灵点/天，同时检查一次性任务与累计积分。适用于用户说"灵犀签到""灵犀任务中心签到""灵犀领积分""灵犀每日签到""领 200 积分""灵点签到""灵犀专业版签到""每天签灵犀"等意图时触发。触发关键词：灵犀签到、灵犀任务中心、灵犀每日签到、灵点签到、lingxi checkin、lingxi.kdocs.cn 签到、灵犀积分。
---

# 灵犀任务中心每日签到

自动化完成 WPS 灵犀（lingxi.kdocs.cn）任务中心的**每日签到**，每次领取 **200 灵点**。

## 前置条件（必须先满足）

1. **浏览器已登录灵犀账号**：本技能依赖浏览器登录态，不做任何登录。打开 `https://lingxi.kdocs.cn` 后页面左上角应能看到积分数字（如「4926」）而非登录按钮。
2. **使用浏览器插件模式操作真实浏览器**（Edge/Chrome 均可，用户已登录的浏览器），不要用内置无头浏览器（无登录态）。
3. 环境：在灵犀 python_cell_exec 环境运行（可加载 browser 技能）。

> 若打开页面后跳到登录页/扫码页/人机验证：属浏览器登录态失效，**停止自动化**，按浏览器登录墙规则征询用户手动登录后再继续。不要擅自输入凭据。

## 每日签到机制（背景）

- 任务中心入口：灵犀 Web 端 / 客户端左下角「礼盒」图标（积分数字右侧）
- 每日签到：`+200 灵点/天`，北京时间 **0 点重置**
- 接口：
  - 状态查询：`GET /api/public/v1/tasks`（同域，携带 Cookie 即可，无需额外令牌）
  - 执行签到：`POST /api/public/v1/tasks/daily_check_in/claim?date=YYYY-MM-DD`
- 判断标准：任务 `task_key === "daily_check_in"` 的 `status` 为 `claimed`=今日已签，`available`=可签
- 一次性任务（专家模式+200 / 群聊+400 / 使用客户端+800）领取后不重复

## 执行流程（推荐：页面内 API 方式，最稳）

1. 加载 browser 技能：
   ```python
   import sys, os
   sys.path.insert(0, os.path.join(os.getenv("SKILL_PATH"), "browser", "scripts"))
   import browser
   ```

2. 打开灵犀 Web 端并等待渲染：
   ```python
   browser.navigate(url="https://lingxi.kdocs.cn/")
   time.sleep(6)  # SPA 渲染需要时间
   ```

3. 关闭可能出现的弹窗（如「SOTA 模型已就绪」等运营弹窗）：用 JS 点击 `aria-label="关闭"` 的按钮，无则跳过。

4. **页面内查状态**（确认登录态 + 今日是否已签）：
   ```javascript
   const r = await fetch('/api/public/v1/tasks', {credentials:'include'});
   const j = await r.json();
   const d = j.data.tasks.find(t => t.task_key === 'daily_check_in');
   return d.status;  // claimed | available
   ```
   - 若 `claimed` → 今日已签到，直接报告「今日已签到（积分 XXX，连续 N 天）」，结束。
   - 若 `available` → 继续签到。
   - 若接口返回 `UserUnauthorized` → 登录态失效，按登录墙规则处理。

5. **执行签到**（页面内 POST，避免 UI 定位脆弱性）：
   ```javascript
   const today = new Date();
   const y = today.getFullYear(), m = String(today.getMonth()+1).padStart(2,'0'), d = String(today.getDate()).padStart(2,'0');
   const r = await fetch('/api/public/v1/tasks/daily_check_in/claim?date=' + y+'-'+m+'-'+d, {method:'POST', credentials:'include'});
   return await r.text();
   ```
   - 成功标志：返回 JSON 中 `result === "ok"`，且 `data.total_claimed_credits` 有值。
   - 若返回提示已签到/不可签到，说明今日已签，按已签到处理。

6. **验证到账**：重新执行第 4 步查状态确认 `claimed`；或读页面左下角积分数字确认 +200。汇总报告：签到状态、今日奖励、累计积分、连续签到天数。

## 备选流程（UI 点击方式，API 异常时兜底）

1. 打开 `https://lingxi.kdocs.cn/` 等待渲染，关闭弹窗。
2. 点击左下角任务中心「礼盒」图标（在积分数字右侧，约第 2 个图标；快照中通常是积分按钮右侧的无文字 button）。
3. 任务中心面板出现「立即签到」按钮 → 点击；若按钮显示「已签到」或「距离下次签到 HH:MM:SS」→ 今日已签。
4. 点击后等待 2~3 秒，观察左下角积分数字是否 +200，面板按钮变为「距离下次签到」即成功。

## 踩坑与判断力

- **页面内 fetch 比 UI 点击稳**：灵犀页面加载慢且布局多变，直接调同域 API（`credentials:'include'`）不受 UI 改版影响；UI 方式仅作兜底。
- **弹窗处理**：首次打开常弹「SOTA 模型就绪/立即体验」等弹窗，遮挡左下角图标，先关掉再操作。
- **0 点重置**：签到在**北京时间**每天 0 点重置，日期参数用当天本地日期即可（页面所在时区即北京时间）。
- **登录态失效**：`/api/public/v1/tasks` 返回 `UserUnauthorized`，或页面出现登录按钮 → 停止并征询用户手动登录，不擅自处理认证。
- **不要重复加分**：确认 `claimed` 后绝不重复调用签到接口。

## 安全红线

- 本技能**不包含也不请求**任何账号、密码、Token、Cookie 等敏感信息；完全依赖用户浏览器的既有登录态。
- 不要在执行中读取、打印或写入任何凭据/Token/个人积分以外的隐私数据。
- 发布/上传前扫描整个技能目录，确保无硬编码密钥。
