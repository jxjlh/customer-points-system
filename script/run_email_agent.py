"""
邮件自动发送 Agent — 一键批量发邮件入口。

工作流程:
  1. 配置/读取 SMTP 邮箱账号
  2. 读取 Excel 收件人列表（自动解析姓氏/名字）
  3. 加载或输入邮件主题/正文模板
  4. 批量渲染模板 → 批量发送邮件

使用方式:
  交互式:  python script/run_email_agent.py
  命令行:  python script/run_email_agent.py --excel ./contacts.xlsx --template ./tpl.txt --dry-run
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# 邮件Agent本身只需要纯文本处理+SMTP，无需视频/FFmpeg等重依赖。
# 这里优先使用独立的 logging 作为 logger，避免被 _shared.py 中的 cv2/numpy 依赖拖垮。
import logging as _logging
_logging.basicConfig(
    level=_logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = _logging.getLogger("email_agent")

# 工具采用惰性加载：只有真正进入交互向导时才导入，
# 确保 --help / --version 等纯 argparse 场景完全零依赖。
_TOOLS: dict[str, Any] = {}


def _load_tools() -> dict[str, Any]:
    """惰性加载邮件工具函数，失败时给出可读的修复建议。"""
    global _TOOLS
    if _TOOLS:
        return _TOOLS
    try:
        from tools.read_email_excel import read_email_excel
        from tools.render_email_template import render_email_template, load_email_template_file
        from tools.send_email_smtp import test_smtp_connection, send_bulk_emails
    except Exception as _tools_err:
        # 如果 tools 包因 cv2/numpy/pandas 等环境问题无法导入，
        # 直接从文件加载，并为这几个模块注入一个最小可用的 _shared 代理。
        import importlib.util, types as _types
        _fake_shared = _types.ModuleType("_shared_fallback")
        _fake_shared.logger = logger
        try:
            from langchain_core.tools import tool as _langchain_tool  # type: ignore
        except Exception:
            def _langchain_tool(f=None, *_, **__):
                def deco(fn):
                    fn.__is_tool__ = True
                    return fn
                return deco if f is None else deco(f)
        _fake_shared.__dict__["tool"] = _langchain_tool
        _fake_pkg = _types.ModuleType("tools")
        _fake_pkg.__path__ = [str(SCRIPT_DIR / "tools")]
        _fake_pkg._shared = _fake_shared  # type: ignore[attr-defined]
        sys.modules.setdefault("tools", _fake_pkg)
        sys.modules.setdefault("tools._shared", _fake_shared)

        def _load_tool_module(name: str, filename: str):
            path = SCRIPT_DIR / "tools" / filename
            spec = importlib.util.spec_from_file_location(f"tools.{name}", str(path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"tools.{name}"] = mod
            mod.__dict__.setdefault("logger", logger)
            mod.__dict__.setdefault("tool", _langchain_tool)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            return mod

        try:
            _mod1 = _load_tool_module("read_email_excel", "read_email_excel.py")
            _mod2 = _load_tool_module("render_email_template", "render_email_template.py")
            _mod3 = _load_tool_module("send_email_smtp", "send_email_smtp.py")
        except Exception as _fallback_err:
            raise RuntimeError(
                f"无法加载邮件工具。\n"
                f"  首次尝试报错: {_tools_err}\n"
                f"  回退模式报错: {_fallback_err}\n"
                f"可能的修复：\n"
                f"  1) 安装邮件Agent依赖: pip install 'pandas>=2.0' 'openpyxl>=3.1'\n"
                f"  2) 如提示numpy/cv2版本冲突，可尝试降级: pip install 'numpy<2'\n"
                f"  3) 或直接使用独立虚拟环境运行本脚本。"
            ) from _fallback_err
        read_email_excel = _mod1.read_email_excel
        render_email_template = _mod2.render_email_template
        load_email_template_file = _mod2.load_email_template_file
        test_smtp_connection = _mod3.test_smtp_connection
        send_bulk_emails = _mod3.send_bulk_emails

    _TOOLS = {
        "read_email_excel": read_email_excel,
        "render_email_template": render_email_template,
        "load_email_template_file": load_email_template_file,
        "test_smtp_connection": test_smtp_connection,
        "send_bulk_emails": send_bulk_emails,
    }
    return _TOOLS


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default else ""
    prompt_text = f"{label}{suffix}: "
    if secret:
        value = getpass.getpass(prompt_text)
    else:
        try:
            value = input(prompt_text).strip()
        except EOFError:
            value = ""
    return value or default


def _env_or_prompt(key: str, label: str, default: str = "", secret: bool = False) -> str:
    from_env = os.environ.get(key, "").strip()
    if from_env:
        return from_env
    return _prompt(label, default, secret)


def interactive_wizard(args: argparse.Namespace) -> int:
    # 进入向导前先加载工具（惰性），如果依赖有问题会在这里给出修复建议。
    tools = _load_tools()
    read_email_excel = tools["read_email_excel"]
    render_email_template = tools["render_email_template"]
    load_email_template_file = tools["load_email_template_file"]
    test_smtp_connection = tools["test_smtp_connection"]
    send_bulk_emails = tools["send_bulk_emails"]

    print("=" * 60)
    print("📧  Crayotter 邮件自动发送 Agent")
    print("=" * 60)
    print()

    # ══════════════════════════════════════════════════════════
    # Step 1: SMTP 配置
    # ══════════════════════════════════════════════════════════
    print("【第 1 步 / 4】邮箱登录配置")
    print("  注意：大部分邮箱（QQ/163/Gmail等）需要使用「SMTP授权码」，而不是登录密码。")
    print("  授权码需要在邮箱设置 → SMTP服务 中开启并生成。")
    print()

    smtp_user = _env_or_prompt("CRAYOTTER_EMAIL_SMTP_USER", "  发件邮箱地址")
    if not smtp_user or "@" not in smtp_user:
        print("  ✗ 邮箱地址格式错误，退出。")
        return 1

    smtp_password = _env_or_prompt("CRAYOTTER_EMAIL_SMTP_PASSWORD", "  SMTP授权码", secret=True)
    if not smtp_password:
        print("  ✗ 授权码不能为空，退出。")
        return 1

    smtp_host = _env_or_prompt("CRAYOTTER_EMAIL_SMTP_HOST", "  SMTP服务器（留空自动识别）", "")
    smtp_port_str = _env_or_prompt("CRAYOTTER_EMAIL_SMTP_PORT", "  SMTP端口（留空自动识别）", "")
    smtp_port = int(smtp_port_str) if smtp_port_str.isdigit() else 0
    sender_name = _env_or_prompt("CRAYOTTER_EMAIL_SENDER_NAME", "  发件人显示名称", smtp_user.split("@")[0])

    print()
    print("  正在测试SMTP连接...")
    test_result_str = test_smtp_connection(
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        sender_name=sender_name,
    )
    test_result = json.loads(test_result_str)
    if test_result.get("status") != "success":
        print(f"  ✗ SMTP连接失败: {test_result.get('message')}")
        if not _prompt("  仍要继续吗？(y/N)", "N").lower().startswith("y"):
            return 1
    else:
        print(f"  ✓ SMTP连接成功 (耗时 {test_result.get('elapsed_seconds', 0)}s)")
        # 使用实际检测到的配置
        smtp_host = test_result.get("smtp_host", smtp_host)
        smtp_port = int(test_result.get("smtp_port", smtp_port))
        use_ssl = test_result.get("use_ssl", True)

    # ══════════════════════════════════════════════════════════
    # Step 2: Excel 收件人
    # ══════════════════════════════════════════════════════════
    print()
    print("【第 2 步 / 4】读取 Excel 收件人列表")
    print("  Excel 至少需要包含「姓名」和「邮箱」两列，其他列可作为模板变量。")
    print()

    excel_path = args.excel or _prompt("  Excel 文件路径 (.xlsx)")
    if not excel_path:
        print("  ✗ 未提供 Excel 路径，退出。")
        return 1
    excel_path = str(Path(excel_path).expanduser().resolve())

    name_column = _prompt("  姓名列名", "姓名")
    email_column = _prompt("  邮箱列名", "邮箱")

    print(f"  正在读取 {excel_path} ...")
    excel_result_str = read_email_excel(
        excel_path=excel_path,
        name_column=name_column,
        email_column=email_column,
    )
    excel_result = json.loads(excel_result_str)
    if excel_result.get("status") != "success":
        print(f"  ✗ 读取Excel失败: {excel_result.get('message')}")
        return 1

    recipients = excel_result.get("recipients", [])
    skipped = excel_result.get("skipped", [])
    print(f"  ✓ 读取成功: 共 {excel_result.get('total')} 行, 有效 {len(recipients)} 人, 跳过 {len(skipped)} 行")
    if recipients:
        sample = recipients[0]
        print(f"  示例数据: 姓名={sample.get('name')}, 姓氏={sample.get('surname')}, 名字={sample.get('given_name')}, 邮箱={sample.get('email')}")
        available_cols = excel_result.get("available_columns", [])
        if available_cols:
            print(f"  可用列/变量: {', '.join(available_cols)}")
    if skipped:
        print(f"  跳过的行: ")
        for s in skipped[:5]:
            print(f"    - 第{s.get('row')}行: {s.get('reason')}")
        if len(skipped) > 5:
            print(f"    ... 还有 {len(skipped) - 5} 行")

    # ══════════════════════════════════════════════════════════
    # Step 3: 邮件模板
    # ══════════════════════════════════════════════════════════
    print()
    print("【第 3 步 / 4】邮件模板配置")
    print("  模板中使用 {{变量名}} 作为占位符，例如：")
    print("    主题: 「{{姓氏}}您好」 — 会自动替换为「张您好」「李您好」")
    print("    常用变量: {{姓名}} {{姓氏}} {{姓}} {{名字}} {{名}} {{邮箱}} + Excel里的所有列")
    print()

    template_path = args.template
    subject = ""
    body = ""
    body_format = "plain"

    if template_path and Path(template_path).exists():
        tpl_result = json.loads(load_email_template_file(template_path))
        if tpl_result.get("status") == "success":
            subject = tpl_result.get("subject", "")
            body = tpl_result.get("body", "")
            body_format = tpl_result.get("body_format", "plain")
            print(f"  ✓ 已加载模板文件: {template_path}")
        else:
            print(f"  ✗ 加载模板失败: {tpl_result.get('message')}")
            template_path = ""

    if not template_path or not (subject or body):
        print("  请输入邮件模板（支持 {{变量}} 占位符）")
        subject = _prompt("  邮件主题", "{{姓氏}}您好，这里是一份重要通知")
        print("  邮件正文（输入完毕后单独输入一行 END 结束）:")
        body_lines = []
        while True:
            try:
                line = input("    ")
            except EOFError:
                break
            if line.strip() == "END":
                break
            body_lines.append(line)
        body = "\n".join(body_lines)
        fmt_input = _prompt("  正文格式 (plain/html)", "plain").lower()
        body_format = "html" if fmt_input.startswith("h") else "plain"

    print(f"  主题预览: {subject}")
    print(f"  正文长度: {len(body)} 字符, 格式: {body_format}")

    # ══════════════════════════════════════════════════════════
    # Step 4: 批量渲染 & 发送
    # ══════════════════════════════════════════════════════════
    print()
    print("【第 4 步 / 4】批量渲染并发送邮件")
    print()

    render_result = json.loads(render_email_template(
        subject_template=subject,
        body_template=body,
        recipients_json=json.dumps(recipients, ensure_ascii=False),
        body_format=body_format,
    ))
    if render_result.get("status") != "success":
        print(f"  ✗ 模板渲染失败: {render_result.get('message')}")
        return 1

    all_missing = render_result.get("all_missing_vars", [])
    if all_missing:
        print(f"  ⚠ 警告：以下变量在Excel中未找到对应列: {', '.join(all_missing)}")
        print(f"    这些变量将保留原样（不会被替换）")
    rendered_emails = render_result.get("rendered_emails", [])
    if rendered_emails:
        sample = rendered_emails[0]
        print(f"  渲染示例 -> {sample.get('name')} <{sample.get('email')}>:")
        print(f"    主题: {sample.get('subject')}")
        preview_body = (sample.get("body") or "")[:120].replace("\n", " ")
        print(f"    正文: {preview_body}{'...' if len(sample.get('body') or '') > 120 else ''}")

    delay_input = _prompt("  每封邮件间隔秒数（防限流）", "1.0")
    try:
        delay_seconds = float(delay_input)
    except ValueError:
        delay_seconds = 1.0

    cc_email = _prompt("  统一抄送邮箱（多人用逗号分隔，留空跳过）", "")
    bcc_email = _prompt("  统一密送邮箱（多人用逗号分隔，留空跳过）", "")

    dry_run = args.dry_run
    if not dry_run:
        confirm = _prompt(
            f"  即将发送 {len(rendered_emails)} 封邮件，先演练不实际发送吗？(Y/n)",
            "Y",
        ).lower()
        dry_run = not confirm.startswith("n")

    if dry_run:
        print(f"  🔍 演练模式：共 {len(rendered_emails)} 封邮件将不会实际发出")
    else:
        confirm_final = _prompt(
            f"  ⚠ 确认实际发送 {len(rendered_emails)} 封邮件到 {smtp_user}？请输入 YES 继续",
            "",
        )
        if confirm_final != "YES":
            print("  已取消。")
            return 0

    print()
    print("  开始执行批量发送...")
    send_result_str = send_bulk_emails(
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        rendered_emails_json=json.dumps(rendered_emails, ensure_ascii=False),
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        use_ssl=use_ssl if "use_ssl" in locals() else "auto",
        sender_name=sender_name,
        cc_email=cc_email,
        bcc_email=bcc_email,
        delay_seconds=delay_seconds,
        stop_on_error=False,
        dry_run=dry_run,
    )
    send_result = json.loads(send_result_str)

    print()
    print("=" * 60)
    print("📊 发送结果汇总")
    print("=" * 60)
    print(f"  总计:     {send_result.get('total', 0)}")
    print(f"  成功:     {send_result.get('success_count', 0)}")
    print(f"  失败:     {send_result.get('failed_count', 0)}")
    print(f"  模式:     {'演练（未实际发送）' if send_result.get('dry_run') else '实际发送'}")
    print(f"  SMTP:     {send_result.get('smtp_host')}:{send_result.get('smtp_port')}")
    print(f"  状态:     {send_result.get('status')}")

    results = send_result.get("results", [])
    failed = [r for r in results if r.get("status") != "success"]
    if failed:
        print()
        print(f"  ✗ 失败明细（{len(failed)} 条）:")
        for r in failed[:20]:
            print(f"    - [{r.get('index')}] {r.get('email')}: {r.get('message')}")
        if len(failed) > 20:
            print(f"    ... 还有 {len(failed) - 20} 条失败记录")

    # 保存结果 JSON 到日志
    try:
        from app.runtime_paths import runtime_path
        logs_dir = runtime_path("logs")
    except Exception:
        logs_dir = SCRIPT_DIR.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = logs_dir / f"email_agent_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "smtp_user": smtp_user,
            "smtp_host": send_result.get("smtp_host"),
            "excel_path": excel_path,
            "subject_template": subject,
            "body_template": body,
            "total": send_result.get("total"),
            "success_count": send_result.get("success_count"),
            "failed_count": send_result.get("failed_count"),
            "dry_run": send_result.get("dry_run"),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print()
    print(f"  📝 详细结果已保存: {out_path}")

    return 0 if send_result.get("failed_count", 0) == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crayotter 邮件自动发送 Agent — 根据Excel和模板一键批量发邮件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
环境变量（可跳过交互）:
  CRAYOTTER_EMAIL_SMTP_USER      发件邮箱
  CRAYOTTER_EMAIL_SMTP_PASSWORD  SMTP授权码
  CRAYOTTER_EMAIL_SMTP_HOST      SMTP服务器（可选）
  CRAYOTTER_EMAIL_SMTP_PORT      SMTP端口（可选）
  CRAYOTTER_EMAIL_SENDER_NAME    发件人显示名称（可选）

示例:
  # 交互式向导
  python script/run_email_agent.py

  # 指定参数
  python script/run_email_agent.py --excel ./contacts.xlsx --template ./tpl.txt

  # 仅演练不实际发送
  python script/run_email_agent.py --excel ./contacts.xlsx --template ./tpl.txt --dry-run
""",
    )
    parser.add_argument("--excel", help="Excel收件人文件路径 (.xlsx)")
    parser.add_argument("--template", help="邮件模板文件路径 (.txt/.md/.html/.json)")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，不实际发送邮件")
    parser.add_argument("--non-interactive", action="store_true", help="非交互模式（必须提供所有必要参数）")
    args = parser.parse_args()

    if args.non_interactive:
        # 简化的非交互模式，缺少参数时直接报错
        missing = []
        if not args.excel:
            missing.append("--excel")
        if not args.template:
            missing.append("--template")
        for key in ("CRAYOTTER_EMAIL_SMTP_USER", "CRAYOTTER_EMAIL_SMTP_PASSWORD"):
            if not os.environ.get(key, "").strip():
                missing.append(f"环境变量 {key}")
        if missing:
            print("非交互模式缺少必要参数:", ", ".join(missing), file=sys.stderr)
            return 1
        # TODO: 实现完整的非交互模式流程
        print("非交互模式将在后续版本支持，请使用交互式模式。")
        return 1

    try:
        return interactive_wizard(args)
    except KeyboardInterrupt:
        print()
        print("用户中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
