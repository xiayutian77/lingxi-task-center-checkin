# -*- coding: utf-8 -*-
"""
灵犀任务中心每日签到脚本
在灵犀 python_cell_exec 环境运行（需先加载 browser 技能）。

用法：
    import lingxi_checkin
    lingxi_checkin.main()

返回：签到结果 dict（status / reward / total_claimed / check_in_days / message）
不含任何敏感信息，仅依赖浏览器既有登录态。
"""

import sys
import os
import time
import json


def _load_browser():
    """加载灵犀 browser 技能对象（幂等）。"""
    sys.path.insert(0, os.path.join(os.getenv("SKILL_PATH"), "browser", "scripts"))
    import browser
    return browser


def _today_str():
    t = time.localtime()
    return "%04d-%02d-%02d" % (t.tm_year, t.tm_mon, t.tm_mday)


def _extract_json(text):
    """从 browser.execute_script 返回值中提取 JSON（其返回值带前缀如 execute_script 成功）。"""
    if not text:
        return None
    # 去掉可能的说明前缀，定位到 JSON 起点
    start = text.find('{')
    if start == -1:
        start = text.find('[')
    if start == -1:
        return None
    # 去除尾部说明/空白
    end = text.rfind('}')
    if end == -1:
        end = text.rfind(']')
    if end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None


def _close_popups(browser):
    """关闭页面上的运营弹窗（如 SOTA 模型就绪等），幂等。"""
    js = r"""
(() => {
  const btns = Array.from(document.querySelectorAll('button'));
  const close = btns.find(b => (b.getAttribute('aria-label')||'').trim() === '关闭');
  if (close) { close.click(); return 'closed'; }
  return 'none';
})()
"""
    try:
        return browser.execute_script(js)
    except Exception:
        return 'none'


def get_tasks(browser):
    """页面内查询任务列表，返回 dict 或 None。"""
    js = r"""
(async () => {
  try {
    const r = await fetch('/api/public/v1/tasks', {credentials:'include'});
    if (!r.ok) return JSON.stringify({http: r.status});
    return await r.text();
  } catch (e) { return JSON.stringify({err: e.message}); }
})()
"""
    raw = browser.execute_script(js)
    data = _extract_json(raw)
    if data is None:
        return None
    if data.get("result") == "UserUnauthorized" or data.get("http"):
        return data
    tasks = (data.get("data") or {}).get("tasks") or []
    daily = next((t for t in tasks if t.get("task_key") == "daily_check_in"), None)
    return {
        "daily": daily,
        "total_claimed_credits": (data.get("data") or {}).get("total_claimed_credits"),
        "raw": data,
    }


def do_checkin(browser):
    """页面内执行每日签到，返回原始响应文本。"""
    js = r"""
(async () => {
  try {
    const t = new Date();
    const date = t.getFullYear() + '-' + String(t.getMonth()+1).padStart(2,'0') + '-' + String(t.getDate()).padStart(2,'0');
    const r = await fetch('/api/public/v1/tasks/daily_check_in/claim?date=' + date, {method:'POST', credentials:'include'});
    return await r.text();
  } catch (e) { return JSON.stringify({err: e.message}); }
})()
"""
    return browser.execute_script(js)


def main(browser=None):
    """完整签到流程，返回结果 dict。"""
    if browser is None:
        browser = _load_browser()

    # 1. 打开灵犀 Web 端
    browser.navigate(url="https://lingxi.kdocs.cn/")
    time.sleep(6)

    # 2. 关闭弹窗
    _close_popups(browser)
    time.sleep(1)

    # 3. 查状态
    st = get_tasks(browser)
    if not st or "daily" not in st:
        if st and st.get("result") == "UserUnauthorized":
            return {"success": False, "message": "登录态失效：灵犀 Web 端未登录，需用户手动登录后再签到"}
        return {"success": False, "message": "无法获取任务状态，可能页面未加载完成或登录失效"}

    daily = st["daily"]
    status = daily.get("status")
    total = st.get("total_claimed_credits")
    reward = daily.get("reward_amount")
    extra = daily.get("extra") or {}
    continuous = extra.get("consecutive_days") or len([d for d in extra.get("check_in_days") or [] if d.get("status") == "claimed"])

    result = {
        "status": status,
        "reward": reward,
        "total_claimed_credits": total,
        "continuous_days": continuous,
        "success": False,
        "message": "",
    }

    if status == "claimed":
        result["success"] = True
        result["message"] = "今日已签到，无需重复（累计获得 %s，连续 %d 天）" % (total, continuous)
        return result

    if status != "available":
        result["message"] = "签到状态异常：%s" % status
        return result

    # 4. 执行签到
    resp_text = do_checkin(browser)
    resp = _extract_json(resp_text)
    if resp is None:
        result["message"] = "签到请求返回异常：" + resp_text[:100]
        return result

    if resp.get("result") == "ok":
        result["success"] = True
        result["message"] = "签到成功（+%s 灵点，累计获得 %s）" % (
            resp.get("data", {}).get("extra", {}).get("today_reward") or reward,
            resp.get("data", {}).get("total_claimed_credits") or total,
        )
    else:
        result["message"] = "签到未成功：" + resp.get("hint", resp_text[:100])

    return result


if __name__ == "__main__":
    res = main()
    print(json.dumps(res, ensure_ascii=False, indent=2))
