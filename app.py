import os
import sys
import traceback
import tempfile
import logging

# 设置日志输出到 stderr（Streamlit Cloud 会捕获 stderr）
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
_log = logging.getLogger("crayotter")
_log.info("=" * 60)
_log.info("Crayotter Streamlit App 启动中...")
_log.info(f"Python: {sys.version}")
_log.info(f"Working dir: {os.getcwd()}")
_log.info(f"App dir: {os.path.dirname(os.path.abspath(__file__))}")
_log.info("=" * 60)

# Ensure app directory is on sys.path BEFORE any other imports
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

# 检测是否在只读文件系统（如 Streamlit Cloud）
def _get_writable_dir():
    """返回可写目录路径，Cloud 环境自动降级到 /tmp"""
    test_path = os.path.join(_APP_DIR, ".write_test")
    try:
        with open(test_path, "w") as f:
            f.write("test")
        os.remove(test_path)
        return _APP_DIR  # 本地开发环境：正常写入
    except (OSError, PermissionError):
        writable = os.path.join(tempfile.gettempdir(), "crayotter_data")
        os.makedirs(writable, exist_ok=True)
        return writable

_WRITABLE_DIR = _get_writable_dir()
_IS_CLOUD = (_WRITABLE_DIR != _APP_DIR)
os.environ["CRAYOTTER_WRITABLE_DIR"] = _WRITABLE_DIR
_log.info(f"Writable dir: {_WRITABLE_DIR} (cloud={_IS_CLOUD})")

import streamlit as st
import textwrap
import pandas as pd
import plotly.express as px
import json, threading, time
from datetime import datetime, timedelta as _timedelta, timezone as _tz, timedelta as _td_
# ⚠️ 中国时区：Streamlit Cloud 服务器在 UTC，所有时间操作必须统一用 UTC+8
TZ_CN = _tz(_td_(hours=8))
def now_cn() -> datetime:
    """返回北京时间（naive datetime 即 datetime 对象不带 tzinfo，但值是北京当地时间）"""
    return datetime.now(tz=TZ_CN).replace(tzinfo=None)
from io import BytesIO
from st_aggrid import AgGrid, GridUpdateMode, DataReturnMode
from st_aggrid.grid_options_builder import GridOptionsBuilder
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
import bcrypt
import base64

# Import app modules with full error diagnostics
try:
    from modules.excel_reader import ExcelReader
    from modules.customer_analysis import CustomerAnalysis
    from modules.point_calculation import PointCalculation
    from modules.database import DatabaseManager
    from modules.invoice_fetcher import InvoiceFetcher
    from modules.quotation_ui import show_quotation
    from modules.db_manager import get_db_manager
    from logo_base64 import get_logo_html, get_avatar_html, get_logo_data_url, get_avatar_data_url
except Exception as e:
    _log.error(f"模块导入失败: {type(e).__name__}: {e}")
    _log.error(traceback.format_exc())
    try:
        st.set_page_config(page_title="诊断错误", layout="wide")
    except Exception:
        pass
    st.error(f"模块导入失败: {type(e).__name__}: {e}")
    st.subheader("诊断信息")
    st.text(f"Python 版本: {sys.version}")
    st.text(f"应用目录: {_APP_DIR}")
    st.text(f"应用目录存在: {os.path.isdir(_APP_DIR)}")
    st.text(f"modules 目录存在: {os.path.isdir(os.path.join(_APP_DIR, 'modules'))}")
    st.text(f"modules/__init__.py 存在: {os.path.isfile(os.path.join(_APP_DIR, 'modules', '__init__.py'))}")
    _modules_dir = os.path.join(_APP_DIR, 'modules')
    if os.path.isdir(_modules_dir):
        st.text(f"modules 目录内容: {os.listdir(_modules_dir)}")
    st.text(f"\nsys.path:")
    for p in sys.path:
        st.text(f"  {p}")
    st.text(f"\n完整错误堆栈:")
    st.code(traceback.format_exc())
    st.stop()

DEFAULT_EXCEL_PATH = os.path.join(_APP_DIR, "2026春夏促销活动清单-7.16.xlsx")
DB_PATH = os.path.join(_WRITABLE_DIR, "database", "points.db")
CONFIG_PATH = os.path.join(_APP_DIR, "config.yaml")
STORAGE_DIR = os.path.join(_WRITABLE_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

# ============================================================
# 📅 定时发送（JSONL持久化 + 轮询tick驱动 + 可选线程）
# 设计要点：
#   · Streamlit Cloud 会 idle 休眠，后台线程(Timer)不可靠
#   · 用前端每 20 秒自动刷新页面触发一次 tick()
#   · tick() 里扫描 JSONL，到点就立刻触发线程发送（不阻塞请求）
# ============================================================
SCHEDULED_QUEUE_PATH = os.path.join(STORAGE_DIR, "scheduled_queue.jsonl")

class ScheduledSender:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.path = SCHEDULED_QUEUE_PATH
        self._thread_locks = {}  # job_id -> 防止同任务重入
        self._global_lock = threading.Lock()

    def _read_all(self):
        rows = []
        if not os.path.exists(self.path):
            return rows
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try: rows.append(json.loads(line))
                    except Exception: pass
        except Exception:
            pass
        return rows

    def _write_all(self, rows):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        except Exception:
            try: os.remove(tmp)
            except: pass

    def upsert(self, job):
        with self._global_lock:
            rows = self._read_all()
            found = False
            for i, r in enumerate(rows):
                if r.get("id") == job.get("id"):
                    rows[i] = {**r, **job}
                    found = True
                    break
            if not found:
                rows.append(job)
            self._write_all(rows)

    def cancel(self, job_id):
        with self._global_lock:
            rows = []
            for r in self._read_all():
                if r.get("id") == job_id:
                    r = dict(r)
                    r["status"] = "cancelled"
                    r["cancelled_at"] = now_cn().isoformat()
                rows.append(r)
            self._write_all(rows)

    def list_jobs(self):
        return self._read_all()

    def _execute(self, row):
        try:
            from modules.email_sender import send_bulk_emails as _sbe
            smtp_user = row.get("smtp_user"); smtp_password = row.get("smtp_password")
            sender_name = row.get("sender_name", "")
            email_list = row.get("email_list") or []
            delay_seconds = float(row.get("delay_seconds", 0) or 0)
            att_refs = row.get("global_attachments_refs") or []
            global_attachments = None
            if att_refs:
                global_attachments = [(base64.b64decode(b64data), name) for name, b64data in att_refs]
            g_cc = row.get("global_cc") or []
            g_bcc = row.get("global_bcc") or []
            is_html = bool(row.get("is_html", False))
            enable_batch = bool(row.get("enable_batch", False))
            batch_size = int(row.get("batch_size", 0) or 0)
            batch_interval = int(row.get("batch_interval", 0) or 0)

            if enable_batch and batch_size > 0 and len(email_list) > batch_size:
                batches = [email_list[i:i+batch_size] for i in range(0, len(email_list), batch_size)]
            else:
                batches = [email_list]

            success_count = 0; fail_count = 0
            for bi, batch in enumerate(batches):
                for i, item in enumerate(batch):
                    try:
                        r = _sbe(
                            smtp_user=smtp_user, smtp_password=smtp_password,
                            email_list=[item], sender_name=sender_name,
                            delay_seconds=0, dry_run=False,
                            global_attachments=global_attachments,
                            global_cc=g_cc, global_bcc=g_bcc, is_html=is_html,
                        )
                        if r.get("success_count", 0) > 0:
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as ie:
                        fail_count += 1
                    if i < len(batch) - 1 and delay_seconds > 0:
                        time.sleep(delay_seconds)
                if bi < len(batches) - 1 and batch_interval > 0:
                    time.sleep(batch_interval * 60)

            updated = dict(row)
            total = len(email_list)
            if fail_count == 0 and success_count > 0:
                updated["status"] = "done"
            elif success_count > 0:
                updated["status"] = "partial"
            else:
                updated["status"] = "failed"
            updated["success_count"] = success_count
            updated["fail_count"] = fail_count
            updated["total"] = total
            updated["finished_at"] = now_cn().isoformat()
            self.upsert(updated)

            if row.get("draft_id"):
                try:
                    drafts = load_drafts() if callable(globals().get("load_drafts", lambda: None)) else []
                    if not drafts and "load_drafts" in globals():
                        drafts = load_drafts()
                    for d in drafts:
                        if d["id"] == row["draft_id"]:
                            d["status"] = "sent"
                            d["sent_at"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
                            d["last_run_summary"] = f"成功{success_count}封，失败{fail_count}封"
                            break
                    if "save_drafts" in globals() and callable(globals()["save_drafts"]):
                        save_drafts(drafts)
                except Exception:
                    pass
        except Exception as e:
            updated = dict(row)
            updated["status"] = "failed"
            updated["error"] = f"{type(e).__name__}: {e}"[:500]
            updated["finished_at"] = now_cn().isoformat()
            self.upsert(updated)

    def tick(self):
        """每次页面 rerun 都触发一次：扫队列 → 到点就开线程发送"""
        with self._global_lock:
            rows = self._read_all()
            now = now_cn()
            changed = False
            for idx, r in enumerate(rows):
                status = r.get("status") or "pending"
                if status in ("done", "failed", "partial", "cancelled", "expired", "running"):
                    continue
                try:
                    scheduled_at = datetime.fromisoformat(r["scheduled_at"])
                except Exception:
                    continue
                wait_secs = (scheduled_at - now).total_seconds()
                job_id = r.get("id")
                if wait_secs < -5 * 60:
                    # 过期 5 分钟以上（错过触发窗口）→ 标记 expired
                    rows[idx] = {**r, "status": "expired",
                                 "error": f"已过期{int(-wait_secs//60)}分钟未触发（请保持页面打开）",
                                 "finished_at": now.isoformat()}
                    changed = True
                elif wait_secs <= 5:
                    # 到达或已过不到5分钟 → 启动发送线程
                    job_id = r.get("id")
                    if job_id in self._thread_locks:
                        continue
                    self._thread_locks[job_id] = True
                    rows[idx] = {**r, "status": "running", "started_at": now.isoformat()}
                    changed = True
                    # 启动后台线程
                    t = threading.Thread(target=self._execute, args=(dict(rows[idx]),), daemon=True)
                    t.start()
            if changed:
                self._write_all(rows)

# 启动实例 & 立刻 tick 一次
_SCHED_SENDER = ScheduledSender.get_instance()
try: _SCHED_SENDER.tick()
except Exception: pass

# 前端自动刷新（每 20s 触发一次 rerun，保证 tick() 能跑到）
def enable_auto_tick_refresh(interval_seconds: int = 20):
    """插入 <iframe> 技巧：其实 Streamlit 有 st_autorefresh，但没有装的话用 meta refresh 兜底"""
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=interval_seconds * 1000, key="schedule_tick_refresh", debounce=False)
        return True
    except Exception:
        # 兜底：用 meta http-equiv refresh（会整页刷新，体验一般但稳）
        st.markdown(
            f'<meta http-equiv="refresh" content="{interval_seconds}" />',
            unsafe_allow_html=True,
        )
        return False


def load_data(excel_path=None, file_bytes=None):
    try:
        if file_bytes:
            excel_reader = ExcelReader(file_bytes=file_bytes)
        elif excel_path:
            excel_reader = ExcelReader(excel_path=excel_path)
        else:
            excel_reader = ExcelReader(excel_path=DEFAULT_EXCEL_PATH)
        
        excel_reader.read_excel()
        
        df_raw = excel_reader.get_raw_data()
        settings = excel_reader.get_settings()
        df_exchange = excel_reader.get_exchange_records()
        column_mapping = excel_reader.get_column_mapping()
        
        customer_analysis = CustomerAnalysis(settings)
        df_customer = customer_analysis.analyze_customer_attributes(df_raw, column_mapping)
        
        point_calculation = PointCalculation(settings)
        df_points = point_calculation.calculate_points(df_raw, df_customer, column_mapping)
        df_account = point_calculation.calculate_point_account(df_points, df_exchange)
        
        db_manager = get_db_manager()
        db_manager.sync_exchange_from_excel(df_exchange)
        
        return {
            "df_raw": df_raw,
            "df_customer": df_customer,
            "df_points": df_points,
            "df_account": df_account,
            "df_exchange": df_exchange,
            "settings": settings,
            "column_mapping": column_mapping,
            "excel_reader": excel_reader
        }
    except Exception as e:
        st.error(f"数据加载失败: {str(e)}")
        return None


def show_home(config):
    from modules.theme import apply_all_styles
    from modules.home_cards import show_home_cards
    
    apply_all_styles()
    
    current_user = st.session_state.get('username')
    is_admin = False
    if current_user and config['credentials']['usernames'].get(current_user, {}).get('role') == 'admin':
        is_admin = True
    
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.markdown(get_logo_html(80), unsafe_allow_html=True)
    with col_title:
        user_display = config['credentials']['usernames'].get(current_user, {}).get('name', current_user) if current_user else ''
        admin_badge = (
            ' <span style="background:#fef3c7;color:#92400e;'
            'padding:2px 8px;border-radius:4px;font-size:12px;margin-left:8px;border:1px solid #fcd34d;">ADMIN</span>'
            if is_admin
            else ""
        )
        st.title("🏠 澄天小助手")
        st.caption(f"欢迎回来，{user_display}{admin_badge}")

    # 极简模式下不再用自定义装饰 banner（渐变/发光/阴影），直接原生 Streamlit
    st.subheader("👋 欢迎使用澄天小助手")
    st.write("一站式管理您的客户积分、邮件、发票和报价，请选择您需要的功能模块：")
    
    # 数据库连接状态检查
    try:
        db_mgr = get_db_manager()
        db_status = db_mgr.get_connection_status()
        if db_status.get('connection_info', {}).get('is_fallback'):
            fallback_reason = db_status.get('connection_info', {}).get('fallback_reason', '未知原因')
            st.info("ℹ️ 使用本地 SQLite 数据库（无需额外配置，数据保存在应用目录）")
            with st.expander("查看数据库诊断信息"):
                st.code(str(db_status), language="text")
                if st.button("🔄 重新检测数据库连接", key="btn-db-diagnose"):
                    st.cache_resource.clear()
                    st.rerun()
        elif db_status.get('db_type', '').startswith('PostgreSQL'):
            st.success("✅ PostgreSQL 数据库连接正常")
        elif db_status.get('db_type', '').startswith('MySQL'):
            st.success("✅ MySQL 数据库连接正常")
        elif db_status.get('db_type', '').startswith('SQLite'):
            st.info("ℹ️ 使用本地 SQLite 数据库")
    except Exception as db_err:
        st.warning(f"⚠️ 数据库初始化异常: {db_err}。请刷新页面重试。")
    
    st.divider()

    cards_config = [
        {
            "icon": "📊",
            "title": "客户积分智能分析",
            "desc": "数据概览 · 客户管理 · 积分管理 · 数据导入 · 报表导出",
            "color_class": "card-blue",
            "key": "btn-customer",
            "session_value": "📊 客户积分智能分析",
            "session_sub": "📈 数据概览",
            "help": "点击进入客户积分智能分析模块",
            "emojis": "📊,✨,💖,⭐,🎉,📈,🏆"
        },
        {
            "icon": "📧",
            "title": "JAX邮件生成器",
            "desc": "自动生成JAX小鼠发货通知邮件",
            "color_class": "card-green",
            "key": "btn-email",
            "session_value": "📧 JAX邮件生成器",
            "help": "点击进入JAX邮件生成器模块",
            "emojis": "📧,✨,🚀,💫,🎉,😄"
        },
        {
            "icon": "🧾",
            "title": "红冲发票自动登记",
            "desc": "自动从邮箱下载并登记电子发票",
            "color_class": "card-orange",
            "key": "btn-invoice",
            "session_value": "🧾 红冲发票自动登记",
            "help": "点击进入红冲发票自动登记模块",
            "emojis": "🧾,✨,💥,🎊,🔥,⭐"
        },
        {
            "icon": "📋",
            "title": "报价助手",
            "desc": "自动查询价格并生成报价单",
            "color_class": "card-purple",
            "key": "btn-quotation",
            "session_value": "📋 报价助手",
            "help": "点击进入报价助手模块",
            "emojis": "💰,✨,💎,⭐,📋,🚀"
        },
        {
            "icon": "🎬",
            "title": "AI 视频剪辑",
            "desc": "Crayotter 多模态Agent · 一句话自动出片",
            "color_class": "card-cyan",
            "key": "btn-video-editor",
            "session_value": "🎬 AI 视频剪辑",
            "help": "点击进入 AI 视频剪辑（Crayotter）模块",
            "emojis": "🎬,✨,🎨,🚀,💫,😄"
        },
        {
            "icon": "📦",
            "title": "库存管理",
            "desc": "物品出入库 · 库存追踪 · 自定义字段",
            "color_class": "card-blue",
            "key": "btn-inventory",
            "session_value": "📦 库存管理",
            "help": "点击进入库存管理模块",
            "emojis": "📦,✨,📊,🔍,💡,🎉"
        },
        {
            "icon": "📨",
            "title": "邮件群发",
            "desc": "Excel批量导入 · 模板变量 · 一键群发",
            "color_class": "card-purple",
            "key": "btn-mass-email",
            "session_value": "📨 邮件群发",
            "help": "点击进入邮件群发模块",
            "emojis": "📨,✨,🚀,💫,🎉,📋"
        },
        {
            "icon": "💾",
            "title": "草稿箱",
            "desc": "邮件草稿管理 · 定时发送 · 编辑重发",
            "color_class": "card-orange",
            "key": "btn-draft-box",
            "session_value": "💾 草稿箱",
            "help": "点击进入草稿箱模块",
            "emojis": "💾,✨,📝,⏰,📤,🎉"
        }
    ]
    
    if is_admin:
        cards_config.append({
            "icon": "👑",
            "title": "用户管理",
            "desc": "查看所有用户信息和登录状态",
            "color_class": "card-pink",
            "key": "btn-admin",
            "session_value": "👑 用户管理",
            "help": "点击进入用户管理模块",
            "emojis": "👑,✨,🎉,🔥,⭐,💎"
        })
    
    show_home_cards(cards_config)


def show_dashboard(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_customer = data["df_customer"]
    df_exchange = data["df_exchange"]
    df_account = data["df_account"]
    settings = data["settings"]
    
    st.title("📊 数据概览")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_points = PointCalculation(settings).get_total_points(df_points)
    total_value = PointCalculation(settings).get_total_point_value(df_points)
    total_exchanged = PointCalculation(settings).get_total_exchanged_points(df_exchange)
    exchange_count = PointCalculation(settings).get_exchange_customer_count(df_exchange)
    
    col1.metric("累计获得积分", f"{total_points:,}")
    col2.metric("积分总价值", f"¥{total_value:,}")
    col3.metric("累计兑换积分", f"{total_exchanged:,}")
    col4.metric("兑换客户数", exchange_count)
    
    col5, col6, col7, col8 = st.columns(4)
    
    new_customers = CustomerAnalysis(settings).get_new_customer_count(df_customer)
    old_customers = CustomerAnalysis(settings).get_old_customer_count(df_customer)
    total_customers = len(df_customer)
    new_ratio = CustomerAnalysis(settings).get_new_customer_ratio(df_customer)
    
    col5.metric("新客户数", new_customers)
    col6.metric("老客户数", old_customers)
    col7.metric("总客户数", total_customers)
    col8.metric("新客户占比", f"{new_ratio}%")
    
    st.subheader("📈 积分趋势分析")
    trend_df = PointCalculation(settings).get_points_trend(df_points)
    
    if not trend_df.empty:
        fig = px.line(trend_df, x="月份", y="积分数量", 
                      title="📉 月度积分获得趋势", 
                      labels={"积分数量": "积分数量", "月份": "月份"},
                      markers=True,
                      color_discrete_sequence=["#00d4ff"],
                      template="plotly_dark")
        fig.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
            hovermode="x unified",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=8, symbol="circle"))
        st.plotly_chart(fig, use_container_width=True)
        
        fig2 = px.bar(trend_df, x="月份", y="订单数",
                      title="📊 月度订单数量",
                      labels={"订单数": "订单数", "月份": "月份"},
                      color="订单数",
                      color_continuous_scale=["#00d4ff", "#00ffd5"],
                      template="plotly_dark")
        fig2.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    st.subheader("🏆 客户积分排名")
    top_customers = PointCalculation(settings).get_top_customers_by_points(df_points)
    
    if not top_customers.empty:
        fig4 = px.bar(top_customers, y="客户", x="累计积分",
                      title="🥇 客户积分排名Top20",
                      labels={"累计积分": "累计积分", "客户": "客户名称"},
                      color="累计积分",
                      color_continuous_scale=["#00d4ff", "#00ffd5"],
                      orientation="h",
                      template="plotly_dark")
        fig4.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            xaxis_title_font=dict(size=14, color="#b8c1ec"),
            yaxis_title_font=dict(size=14, color="#b8c1ec"),
            height=500,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=120, r=50, t=60, b=50)
        )
        fig4.update_traces(
            hovertemplate="客户: %{y}<br>累计积分: %{x:,}",
            marker=dict(line=dict(width=0))
        )
        st.plotly_chart(fig4, use_container_width=True)
        
        st.subheader("📋 客户积分排名详情")
        gb = GridOptionsBuilder.from_dataframe(top_customers)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(top_customers, gridOptions=grid_options, height=300,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("👥 客户属性分布")
    if not df_customer.empty:
        attribute_counts = df_customer["客户属性"].value_counts()
        
        fig3 = px.pie(values=attribute_counts.values, names=attribute_counts.index,
                      title="👨‍👩‍👧‍👦 新老客户分布",
                      hole=0.4,
                      color_discrete_sequence=["#00d4ff", "#00ffd5"],
                      template="plotly_dark")
        fig3.update_layout(
            title_font=dict(size=18, color="#b8c1ec"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=50, r=50, t=60, b=50)
        )
        fig3.update_traces(
            hoverinfo="label+percent+value",
            textinfo="label+percent",
            textfont=dict(size=14),
            marker=dict(line=dict(color="#1a1f3a", width=2))
        )
        st.plotly_chart(fig3, use_container_width=True)


def show_customer_management(data):
    if data is None:
        return
    
    df_customer = data["df_customer"]
    df_account = data["df_account"]
    
    st.title("👥 客户管理")
    
    st.subheader("客户列表")
    if not df_customer.empty:
        gb = GridOptionsBuilder.from_dataframe(df_customer)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_customer, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("客户积分账户")
    if not df_account.empty:
        gb = GridOptionsBuilder.from_dataframe(df_account)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_account, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("客户搜索")
    search_name = st.text_input("输入客户名称搜索")
    
    if search_name:
        filtered = df_customer[df_customer["客户"].str.contains(search_name, na=False)]
        if not filtered.empty:
            st.dataframe(filtered)
        else:
            st.warning("未找到匹配的客户")


def show_point_management(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_exchange = data["df_exchange"]
    settings = data["settings"]
    
    st.title("🏆 积分管理")
    
    st.subheader("积分明细")
    if not df_points.empty:
        gb = GridOptionsBuilder.from_dataframe(df_points)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_points, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("积分兑换记录")
    if not df_exchange.empty:
        gb = GridOptionsBuilder.from_dataframe(df_exchange)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar()
        gb.configure_default_column(editable=False)
        
        grid_options = gb.build()
        AgGrid(df_exchange, gridOptions=grid_options, height=400,
               data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
               update_mode=GridUpdateMode.NO_UPDATE,
               fit_columns_on_grid_load=True)
    
    st.subheader("积分参数设置")
    col1, col2, col3 = st.columns(3)
    
    new_multiplier = col1.number_input("新客户积分倍率", min_value=1, max_value=10, 
                                       value=int(settings.get("新客户积分倍率", 2)))
    old_multiplier = col2.number_input("老客户积分倍率", min_value=1, max_value=10,
                                       value=int(settings.get("老客户积分倍率", 1)))
    exchange_rate = col3.number_input("积分兑换比例", min_value=0.1, max_value=1.0,
                                      value=float(settings.get("积分兑换比例", 0.3)), step=0.1)
    
    if st.button("保存设置"):
        settings["新客户积分倍率"] = new_multiplier
        settings["老客户积分倍率"] = old_multiplier
        settings["积分兑换比例"] = exchange_rate
        st.success("设置已保存")
    
    st.subheader("兑换趋势")
    exchange_trend = PointCalculation(settings).get_exchange_trend(df_exchange)
    
    if not exchange_trend.empty:
        fig = px.line(exchange_trend, x="月份", y="兑换积分",
                      title="月度兑换积分趋势",
                      markers=True)
        st.plotly_chart(fig, use_container_width=True)


def show_data_import():
    st.title("📥 数据导入")
    
    st.subheader("上传Excel文件")
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                data = load_data(file_bytes=uploaded_file.getvalue())
                if data:
                    st.success("数据导入成功！")
                    st.session_state['data'] = data
                    
                    st.subheader("导入数据预览")
                    st.dataframe(data["df_raw"].head(20))
                    
                    st.download_button(
                        label="下载导入的数据",
                        data=uploaded_file.getvalue(),
                        file_name=f"导入数据_{now_cn().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"数据导入失败: {str(e)}")
    
    st.subheader("使用默认数据")
    if st.button("加载默认数据"):
        with st.spinner("正在加载默认数据..."):
            try:
                data = load_data()
                if data:
                    st.success("默认数据加载成功！")
                    st.session_state['data'] = data
            except Exception as e:
                st.error(f"加载默认数据失败: {str(e)}")


def show_reports(data):
    if data is None:
        return
    
    df_points = data["df_points"]
    df_customer = data["df_customer"]
    df_exchange = data["df_exchange"]
    settings = data["settings"]
    
    st.title("📝 报表导出")
    
    st.subheader("选择报表类型")
    report_type = st.selectbox("请选择报表类型", [
        "客户积分汇总报表",
        "积分兑换明细报表",
        "客户属性分析报表",
        "积分趋势报表"
    ])
    
    if st.button("生成报表"):
        buffer = BytesIO()
        
        if report_type == "客户积分汇总报表":
            top_customers = PointCalculation(settings).get_top_customers_by_points(df_points)
            
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                top_customers.to_excel(writer, sheet_name="客户积分排名", index=False)
                data["df_account"].to_excel(writer, sheet_name="客户积分账户", index=False)
        
        elif report_type == "积分兑换明细报表":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_exchange.to_excel(writer, sheet_name="积分兑换记录", index=False)
        
        elif report_type == "客户属性分析报表":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_customer.to_excel(writer, sheet_name="客户属性分析", index=False)
        
        elif report_type == "积分趋势报表":
            trend_df = PointCalculation(settings).get_points_trend(df_points)
            exchange_trend = PointCalculation(settings).get_exchange_trend(df_exchange)
            
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                trend_df.to_excel(writer, sheet_name="积分获得趋势", index=False)
                exchange_trend.to_excel(writer, sheet_name="积分兑换趋势", index=False)
        
        buffer.seek(0)
        
        st.download_button(
            label="下载报表",
            data=buffer,
            file_name=f"{report_type}_{now_cn().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success("报表生成成功！")


def validate_columns_email(df):
    required_columns = [
        "Job No",
        "Individual PO Number",
        "JAX销售",
        "单位名称",
        "品系号",
        "年龄",
        "性别",
        "数量",
        "发运笼数",
        "隔离后预估笼数",
        "实际出运笼数",
        "提货时间",
        "承运方",
        "城市",
        "收货人",
        "送货地址",
        "拟收货时间",
        "收货备注"
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Excel文件缺少必要的列：{', '.join(missing_columns)}")


def read_shipping_list(file_bytes):
    """从发货清单子表读取小鼠详细信息（货号、基因型、性别、周龄、数量）"""
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheet_names = xls.sheet_names
    debug_info = f"所有子表: {sheet_names}\n"
    
    # 查找发货清单子表 - 按名称匹配
    target_sheet = None
    for name in sheet_names:
        if "发货清单" in name or "shipping" in name.lower() or "Shipping" in name:
            target_sheet = name
            break
    # 没找到则用第二个子表
    if target_sheet is None and len(sheet_names) > 1:
        target_sheet = sheet_names[1]
    if target_sheet is None:
        return pd.DataFrame(), debug_info + "未找到发货清单子表"
    
    debug_info += f"使用子表: {target_sheet}\n"
    df_raw = pd.read_excel(xls, sheet_name=target_sheet, header=None)
    debug_info += f"行数: {len(df_raw)}, 列数: {len(df_raw.columns)}\n"
    
    # 预览前15行
    debug_info += "\n前15行预览:\n"
    for idx in range(min(15, len(df_raw))):
        row_vals = [str(v)[:25] for v in df_raw.iloc[idx].tolist()]
        debug_info += f"  行{idx}: {row_vals}\n"
    
    # 列别名映射
    field_aliases = {
        "货号": ["Stock Number", "Strock Number", "stock number", "货号", "Stock_No", "StockNumber", "stock"],
        "基因型": ["Genotype", "genotype", "基因型", "GENOTYPE"],
        "性别": ["SEX", "Sex", "sex", "性别"],
        "年龄": ["AGE", "Age", "age", "年龄", "周龄"],
        "数量": ["Qty", "qty", "QTY", "数量", "Quantity", "quantity"],
        "Individual PO Number": ["Individual PO Number", "PO Number", "Individual_PO_Number", "Individual PO"],
        "Job No": ["Job No", "Job_No", "JobNo", "job no"],
    }
    
    # 扫描每一行找表头
    header_idx = None
    found_cols = {}
    
    for idx, row in df_raw.iterrows():
        row_values = [str(v).strip() for v in row.tolist()]
        temp_found = {}
        for field, aliases in field_aliases.items():
            for col_idx, val in enumerate(row_values):
                if val in aliases or val.lower() in [a.lower() for a in aliases]:
                    temp_found[field] = (col_idx, val)
                    break
        # 找到货号+数量即认为是表头行
        if "货号" in temp_found and "数量" in temp_found:
            header_idx = idx
            found_cols = temp_found
            break
    
    if header_idx is None:
        return pd.DataFrame(), debug_info + "\n未找到包含Stock Number和Qty的表头行"
    
    debug_info += f"\n表头行: 行{header_idx}\n"
    debug_info += f"匹配到的列: "
    for field, (col_idx, col_name) in found_cols.items():
        debug_info += f"\n  {field} → 列{col_idx} ({col_name})"
    debug_info += "\n"
    
    # 读取数据
    df_data = df_raw.iloc[header_idx + 1:].copy().reset_index(drop=True)
    
    # 构建结果DataFrame
    result = pd.DataFrame()
    for field, (col_idx, _) in found_cols.items():
        result[field] = df_data.iloc[:, col_idx]
    
    # 清理：去掉全空行、表头重复行
    result = result.dropna(how='all')
    if "数量" in result.columns:
        result = result[result["数量"].notna()]
        result = result[result["数量"].astype(str).str.strip() != ""]
        result = result[~result["数量"].astype(str).str.contains("Qty|数量|Quantity", na=False, case=False)]
    if "货号" in result.columns:
        result = result[result["货号"].notna()]
        result = result[result["货号"].astype(str).str.strip() != ""]
        result = result[~result["货号"].astype(str).str.contains("Stock|货号", na=False, case=False)]
    
    # 数量转数值
    if "数量" in result.columns:
        result["数量"] = pd.to_numeric(result["数量"], errors='coerce')
        result = result.dropna(subset=["数量"])
    
    result = result.reset_index(drop=True)
    
    debug_info += f"\n提取数据行数: {len(result)}\n"
    if len(result) > 0:
        debug_info += f"\n前5行数据:\n{result.head().to_string()}\n"
    
    return result, debug_info


def format_date_email(date_value):
    if pd.isna(date_value):
        return ""
    
    import re
    
    # 如果是datetime对象
    if hasattr(date_value, 'month') and hasattr(date_value, 'day'):
        return f"{date_value.month}月{date_value.day}日"
    
    # 尝试用pandas统一转换
    try:
        date_obj = pd.to_datetime(date_value)
        return f"{date_obj.month}月{date_obj.day}日"
    except (ValueError, TypeError):
        pass
    
    # 字符串处理
    if isinstance(date_value, str):
        clean_str = str(date_value).strip()
        
        # 处理非标准格式如 "18上午5:00" 或 "8月19日上午5:00"
        # 用正则提取所有连续数字
        numbers = re.findall(r'\d+', clean_str)
        
        # 尝试标准格式
        if '-' in clean_str or '/' in clean_str:
            try:
                date_obj = pd.to_datetime(clean_str)
                return f"{date_obj.month}月{date_obj.day}日"
            except:
                pass
        
        # 处理中文日期格式 "X月X日"
        month_match = re.search(r'(\d+)月', clean_str)
        day_match = re.search(r'(\d+)日', clean_str)
        if month_match and day_match:
            return f"{month_match.group(1)}月{day_match.group(1)}日"
        
        # 只有日的情况 "18上午5:00"
        if len(numbers) >= 1:
            # 取第一个数字作为日
            return f"{numbers[0]}日"
        
        return clean_str
    
    return str(date_value)


def build_strain_list(group_df):
    """构建小鼠列表文本
    新格式：您订购的JAX小鼠# {货号},基因型：{基因型} -性别：{性别} -发货周龄：{周龄} -数量：{数量}
    返回字符串列表，每个元素代表一组小鼠
    """
    # 确保必要列存在
    if "货号" not in group_df.columns:
        group_df["货号"] = ""
    if "基因型" not in group_df.columns:
        group_df["基因型"] = ""
    if "性别" not in group_df.columns:
        group_df["性别"] = ""
    if "年龄" not in group_df.columns:
        group_df["年龄"] = ""
    if "数量" not in group_df.columns:
        group_df["数量"] = 1

    # 分组：货号+基因型+性别相同则合并数量
    group_keys = ["货号", "基因型", "性别"]
    grouped = group_df.groupby(group_keys, dropna=False)

    lines = []
    for key_tuple, group in grouped:
        stock = str(key_tuple[0]).strip() if key_tuple[0] is not None else ""
        if stock.lower() in ("nan", "none", ""):
            stock = ""
        genotype = str(key_tuple[1]).strip() if key_tuple[1] is not None else ""
        if genotype.lower() in ("nan", "none"):
            genotype = ""
        sex = str(key_tuple[2]).strip() if key_tuple[2] is not None else ""

        # 数量合并
        qty_vals = pd.to_numeric(group["数量"], errors='coerce')
        qty = qty_vals.sum()
        if pd.isna(qty) or qty == 0:
            qty = len(group)
        qty = int(qty) if float(qty).is_integer() else qty

        # 年龄取第一条
        first_row = group.iloc[0]
        age = str(first_row["年龄"]).strip() if pd.notna(first_row["年龄"]) else ""
        if age.lower() in ("nan", "none"):
            age = ""

        # 性别转换
        if sex.upper() in ("F", "FEMALE") or sex == "雌":
            sex_text = "雌"
        elif sex.upper() in ("M", "MALE") or sex == "雄":
            sex_text = "雄"
        else:
            sex_text = sex

        # 周龄
        age_text = f"{age}周" if age else ""

        line = f"您订购的JAX小鼠# {stock},基因型：{genotype} -性别：{sex_text} -发货周龄：{age_text} -数量：{qty}"
        lines.append(line)

    return lines


def render_mail(surname, strain_lines, receive_date, delivery_address):
    """生成邮件正文
    每组小鼠一行，最后一行连接"预计将在..."配送信息
    """
    if not strain_lines:
        strain_lines = ["（未找到小鼠信息）"]

    if len(strain_lines) == 1:
        strain_text = strain_lines[0] + f" ，预计将在{receive_date}下午17:00前送到您合同指定收货地址：{delivery_address}。请问当天是否方便接收小鼠呢？"
    else:
        parts = []
        for i, line in enumerate(strain_lines):
            if i < len(strain_lines) - 1:
                parts.append(line + "。")
            else:
                parts.append(line + f" ，预计将在{receive_date}下午17:00前送到您合同指定收货地址：{delivery_address}。请问当天是否方便接收小鼠呢？")
        strain_text = "\n".join(parts)

    mail_body = f"""尊敬的{surname}老师：

您好！

本封邮件为JAX小鼠配送通知。

{strain_text}

附件是本批小鼠的相关文件：美国健康证书AHC，JAX鼠房微生物报告， 隔离场微生物报告以及JAX小鼠接收指南。

为了确保小鼠在接收后可以尽快的服务于您的研究，建议您：

1.严格遵照随附的《JAX 小鼠接收指南》开展相关操作。小鼠签收时，请即刻检查外包装完整性，并仔细核验小鼠核心信息（品系、数量、性别等）。所有问题须在24 小时内反馈至北京澄天生物科技有限公司，逾期将视为验收合格。请注意，退款及补发政策申请需满足以下条件：相关问题需在小鼠送达贵单位后48 小时内，由贵方提供有效证明材料并提交反馈；后续需经北京澄天生物科技有限公司及JAX 联合核验通过，方可启动对应流程。

2. 建议您收到小鼠后尽快按照官网上提供的基因鉴定方案对小鼠进行鉴定核实，以便于您后续合理的制定繁育/使用方案。

若有问题欢迎随时与我们联系。

预祝您实验一切顺利！"""

    return mail_body


def process_excel_email(file_bytes):
    # 1. 读取出隔离场 - 获取PO级别的收货地址、提货人、拟收货时间
    df = pd.read_excel(BytesIO(file_bytes), sheet_name='出隔离场', header=None)

    header_row_index = None
    for idx, row in df.iterrows():
        first_cell = str(row.iloc[0]).strip()
        if first_cell == "Job No":
            second_cell = str(row.iloc[1]).strip()
            if second_cell == "Individual PO Number":
                third_cell = str(row.iloc[2]).strip()
                if third_cell == "JAX销售":
                    header_row_index = idx
                    break

    if header_row_index is None:
        raise ValueError("未找到表头行，请确保Excel文件包含正确的表头")

    new_header = df.iloc[header_row_index].tolist()
    df = df.iloc[header_row_index + 2:]
    df.columns = new_header

    df = df.dropna(how='all')
    df = df[~df["Job No"].astype(str).str.contains("Job No|Quantity", na=False)]

    # 2. 读取发货清单 - 获取小鼠详细信息
    shipping_df, ship_debug = read_shipping_list(file_bytes)

    debug_info = "========== 发货清单读取 ==========\n" + ship_debug + "\n"

    # 3. 构建 Job No → PO 映射（用于关联发货清单和出隔离场）
    job_to_po = {}
    if "Job No" in df.columns and "Individual PO Number" in df.columns:
        for _, row in df.iterrows():
            job = str(row["Job No"]).strip() if pd.notna(row["Job No"]) else ""
            po = str(row["Individual PO Number"]).strip() if pd.notna(row["Individual PO Number"]) else ""
            if job and po and job.lower() not in ("nan", ""):
                job_to_po[job] = po

    debug_info += f"出隔离场 Job No→PO 映射: {len(job_to_po)}条\n"

    # 4. 为发货清单数据补充PO信息
    if len(shipping_df) > 0:
        if "Individual PO Number" not in shipping_df.columns:
            # 尝试用Job No关联
            if "Job No" in shipping_df.columns:
                shipping_df["Individual PO Number"] = shipping_df["Job No"].astype(str).str.strip().map(job_to_po).fillna("")
                debug_info += f"用Job No关联PO，匹配{(shipping_df['Individual PO Number'] != '').sum()}条\n"
            else:
                shipping_df["Individual PO Number"] = ""
                debug_info += "发货清单无PO和Job No列，无法关联\n"

    # 5. 为每个PO生成邮件
    po_order = df["Individual PO Number"].dropna().unique().tolist()

    result_rows = []
    for po_number in po_order:
        po_rows = df[df["Individual PO Number"] == po_number]
        first_row = po_rows.iloc[0]

        # 收货地址（从出隔离场的"送货地址"列）
        delivery_address = ""
        if "送货地址" in po_rows.columns:
            delivery_address = str(first_row["送货地址"]).strip() if pd.notna(first_row["送货地址"]) else ""

        # 提货人 → 姓氏（优先提货人，其次收货人）
        contact = ""
        if "提货人" in po_rows.columns:
            contact = str(first_row["提货人"]).strip() if pd.notna(first_row["提货人"]) else ""
        if not contact or contact.lower() in ("nan", ""):
            if "收货人" in po_rows.columns:
                contact = str(first_row["收货人"]).strip() if pd.notna(first_row["收货人"]) else ""
        surname = contact[0] if contact and contact.lower() not in ("nan", "") else ""

        # 拟收货时间
        receive_date = ""
        if "拟收货时间" in po_rows.columns:
            receive_date = format_date_email(first_row["拟收货时间"]) if pd.notna(first_row["拟收货时间"]) else ""

        # 从发货清单获取该PO的小鼠信息
        po_mice = pd.DataFrame()
        if len(shipping_df) > 0 and "Individual PO Number" in shipping_df.columns:
            po_mice = shipping_df[
                shipping_df["Individual PO Number"].astype(str).str.strip() == str(po_number).strip()
            ].copy()

        debug_info += f"\nPO {po_number}: 发货清单匹配{len(po_mice)}条小鼠记录\n"

        if len(po_mice) == 0:
            strain_lines = []
        else:
            strain_lines = build_strain_list(po_mice)

        mail_body = render_mail(surname, strain_lines, receive_date, delivery_address)

        result_rows.append({
            "Individual PO Number": po_number,
            "单位名称": first_row.get("单位名称", ""),
            "收货人": contact,
            "邮件内容": mail_body
        })

    result_df = pd.DataFrame(result_rows)
    result_df['po_order'] = result_df['Individual PO Number'].map(lambda x: po_order.index(x) if x in po_order else len(po_order))
    result_df = result_df.sort_values('po_order').drop('po_order', axis=1)

    # 保存调试信息
    process_excel_email._debug_info = debug_info

    return result_df


def show_email_generator():
    from modules.email_sender import test_smtp_connection, send_bulk_emails, guess_smtp_config, list_smtp_candidates

    st.title("📧 JAX小鼠发货通知邮件生成器")

    st.markdown(textwrap.dedent(
        """
    **使用说明：**
    1. 上传Excel文件（需包含【出隔离场】和【发货清单】Sheet）
    2. 小鼠详细信息（货号、基因型、性别、周龄、数量）从「发货清单」读取
    3. 收货地址、提货人、拟收货时间从「出隔离场」读取
    4. 配置SMTP后可直接批量发送邮件
    """))

    with st.expander("🔐 SMTP邮箱配置", expanded=False):
        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            smtp_user = st.text_input("邮箱地址", value=st.session_state.get("email_smtp_user", "1392039316@qq.com"), key="eg_smtp_user")
        with cfg_col2:
            smtp_password = st.text_input("SMTP授权码", type="password", value=st.session_state.get("email_smtp_password", "dtepljmsauzgjbfa"), key="eg_smtp_password")
        with cfg_col3:
            sender_name = st.text_input("发件人名称", value=st.session_state.get("email_sender_name", "Cindy 张茹"), key="eg_sender_name")

        if smtp_user:
            host, port, ssl_flag = guess_smtp_config(smtp_user)
            st.caption(f"自动识别SMTP: {host}:{port} {'(SSL)' if ssl_flag else '(STARTTLS)'}")

        with st.expander("🛠️ 高级：手动覆盖SMTP服务器", expanded=False):
            override_col1, override_col2, override_col3 = st.columns(3)
            with override_col1:
                manual_host = st.text_input("SMTP主机（留空用自动识别）", value=st.session_state.get("eg_smtp_host", ""), key="eg_manual_host", placeholder="例如 smtp.qiye.163.com")
            with override_col2:
                manual_port_input = st.text_input("端口（留空用自动识别）", value=str(st.session_state.get("eg_smtp_port", "") or ""), key="eg_manual_port", placeholder="例如 465")
            with override_col3:
                manual_ssl = st.checkbox("使用SSL（465/994）", value=st.session_state.get("eg_smtp_ssl", True), key="eg_manual_ssl")
            candidates = list_smtp_candidates(smtp_user) if smtp_user else []
            if len(candidates) > 1:
                st.caption("常见候选（企业域名不确定时可尝试）：" + "；".join([f"{c[3]} {c[0]}:{c[1]}" for c in candidates[1:]]))

        eff_host = manual_host.strip() or host
        try:
            eff_port = int(str(manual_port_input).strip()) if str(manual_port_input).strip() else port
        except Exception:
            eff_port = port
        eff_ssl = manual_ssl

        test_col1, test_col2 = st.columns([1, 3])
        with test_col1:
            if st.button("🔌 测试连接", key="eg_test_conn"):
                with st.spinner("测试SMTP连接..."):
                    conn_result = test_smtp_connection(smtp_user, smtp_password, eff_host, eff_port)
                    if conn_result["status"] == "success":
                        st.success(f"✅ 连接成功！{conn_result['smtp_host']}:{conn_result['smtp_port']} ({conn_result['elapsed_seconds']}s)")
                    else:
                        st.error(f"❌ 连接失败: {conn_result.get('message', '未知错误')}")
                        candidates = list_smtp_candidates(smtp_user)
                        if len(candidates) > 1:
                            st.info(f"💡 自动识别未命中，请在「高级」里手动指定。常见候选：" + "；".join([f"{c[3]} {c[0]}:{c[1]}" for c in candidates[1:]]))

        st.session_state["email_smtp_user"] = smtp_user
        st.session_state["email_smtp_password"] = smtp_password
        st.session_state["email_sender_name"] = sender_name
        st.session_state["eg_smtp_host"] = manual_host
        st.session_state["eg_smtp_port"] = str(manual_port_input or "")
        st.session_state["eg_smtp_ssl"] = manual_ssl
        st.session_state["eg_smtp_eff_host"] = eff_host
        st.session_state["eg_smtp_eff_port"] = eff_port
        st.session_state["eg_smtp_eff_ssl"] = eff_ssl

    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"])

    if uploaded_file is not None:
        with st.spinner("正在处理Excel文件..."):
            try:
                result_df = process_excel_email(uploaded_file.getvalue())

                st.success(f"邮件生成完成！共 {len(result_df)} 封邮件")

                debug_info = getattr(process_excel_email, '_debug_info', '')

                with st.expander("🔍 调试信息（发货清单解析详情）", expanded=False):
                    if debug_info:
                        st.text(debug_info)
                    else:
                        st.info("无调试信息")

                st.subheader("生成的邮件列表")
                st.dataframe(result_df, width="stretch", height=300)

                excel_buffer = BytesIO()
                result_df.to_excel(excel_buffer, index=False, sheet_name="邮件生成结果")
                excel_buffer.seek(0)

                st.download_button(
                    label="📥 下载邮件结果",
                    data=excel_buffer,
                    file_name=f"JAX邮件生成结果_{now_cn().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                st.subheader("📧 邮件预览")
                for _, row in result_df.iterrows():
                    with st.expander(f"📧 {row['Individual PO Number']} - {row['单位名称']}"):
                        st.text(row['邮件内容'])

                st.divider()

                st.subheader("📤 批量发送邮件")

                send_col1, send_col2 = st.columns([1, 2])
                with send_col1:
                    delay_seconds = st.number_input("发送间隔(秒)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="eg_delay")
                    dry_run = st.checkbox("演练模式（不实际发送）", value=True, key="eg_dry_run")
                    with st.expander("👥 抄送 / 密抄", expanded=False):
                        eg_cc_text = st.text_area(
                            "抄送 CC（发货通知抄送给谁）",
                            value=st.session_state.get("eg_cc_text", ""),
                            key="eg_cc_input", height=50,
                            placeholder="每行一个，或逗号分隔",
                        )
                        eg_bcc_text = st.text_area(
                            "密抄 BCC（自己备份/领导签收，收件人不可见）",
                            value=st.session_state.get("eg_bcc_text", ""),
                            key="eg_bcc_input", height=50,
                            placeholder="每行一个，或逗号分隔",
                        )
                        st.session_state["eg_cc_text"] = eg_cc_text
                        st.session_state["eg_bcc_text"] = eg_bcc_text
                with send_col2:
                    eg_attachment_files = st.file_uploader(
                        "📎 添加附件（每封发货通知都会带上，支持多文件）",
                        type=None, accept_multiple_files=True, key="eg_attachments",
                        help="随发货通知一起发送：发票、装箱单、品系说明等。"
                    )
                    if eg_attachment_files:
                        total_kb = sum(f.size for f in eg_attachment_files) / 1024
                        st.caption(f"已选 {len(eg_attachment_files)} 个附件，共 {total_kb:.1f} KB")

                recipient_emails = st.text_area(
                    "收件人邮箱列表（每行一个，对应上面邮件列表顺序）",
                    key="eg_recipients",
                    height=100,
                    placeholder="heng.li@lab-direct.com\niblcs01@ibiologistics.com\n..."
                )

                email_list_for_send = []
                for idx, row in result_df.iterrows():
                    lines = recipient_emails.strip().split("\n") if recipient_emails.strip() else []
                    to_email = lines[idx].strip() if idx < len(lines) else ""
                    if to_email:
                        email_list_for_send.append({
                            "email": to_email,
                            "name": row.get("收货人", ""),
                            "subject": f"JAX小鼠发货通知 - {row['Individual PO Number']}",
                            "body": row["邮件内容"],
                        })

                # 构造全局附件
                eg_global_attachments = None
                if eg_attachment_files:
                    eg_global_attachments = []
                    for uf in eg_attachment_files:
                        uf.seek(0)
                        eg_global_attachments.append((uf.read(), uf.name))

                # 全局 Cc / Bcc
                from modules.email_sender import _normalize_addrs as _norm_eg
                eg_g_cc = _norm_eg(eg_cc_text)
                eg_g_bcc = _norm_eg(eg_bcc_text)

                if email_list_for_send:
                    info_parts = [f"待发送 {len(email_list_for_send)} 封邮件"]
                    if eg_global_attachments:
                        info_parts.append(f"每封附加 {len(eg_global_attachments)} 个文件")
                    if eg_g_cc: info_parts.append(f"抄送×{len(eg_g_cc)}")
                    if eg_g_bcc: info_parts.append(f"密抄×{len(eg_g_bcc)}")
                    st.info("，".join(info_parts))
                    short_list = email_list_for_send[:15]
                    st.caption("预览名单：" + "；".join(
                        f"{r['name']}→{r['email']}" for r in short_list
                    ) + (" 等" if len(email_list_for_send) > len(short_list) else ""))
                    if eg_g_cc or eg_g_bcc:
                        parts = []
                        if eg_g_cc: parts.append("👁️ CC：" + "、".join(eg_g_cc))
                        if eg_g_bcc: parts.append("🕵️ BCC：" + "、".join(eg_g_bcc) + "（收件人不可见）")
                        st.caption("   ".join(parts))

                    # 预览数量切换（默认全部）
                    eg_preview_options = [("全部", len(email_list_for_send))]
                    for n in [10, 50]:
                        if len(email_list_for_send) > n:
                            eg_preview_options.append((f"前 {n} 封", n))
                    eg_preview_labels = [o[0] for o in eg_preview_options]
                    eg_preview_values = [o[1] for o in eg_preview_options]
                    eg_preview_idx = st.selectbox(
                        "📧 预览数量",
                        range(len(eg_preview_options)),
                        format_func=lambda i: eg_preview_labels[i],
                        index=0, key="eg_preview_limit",
                    )
                    eg_preview_limit = eg_preview_values[eg_preview_idx]
                    with st.expander(f"📧 预览前 {min(eg_preview_limit, len(email_list_for_send))} 封（共 {len(email_list_for_send)} 封）", expanded=False):
                        for item in email_list_for_send[:eg_preview_limit]:
                            st.markdown(f"**{item['name']}** ({item['email']})　•　主题：{item['subject']}")
                            extras = []
                            if eg_g_cc: extras.append("👁️ CC：" + "、".join(eg_g_cc))
                            if eg_g_bcc: extras.append("🕵️ BCC：" + "、".join(eg_g_bcc))
                            if eg_global_attachments:
                                names = [a[1] for a in eg_global_attachments] if isinstance(eg_global_attachments[0], tuple) else [str(a) for a in eg_global_attachments]
                                extras.append("📎 " + "、".join(names))
                            if extras: st.caption("　".join(extras))
                            st.text(item['body'][:500] + ("..." if len(item['body']) > 500 else ""))
                            st.divider()

                    if st.button("🚀 " + ("演练预览" if dry_run else "立即发送"), key="eg_send", type="primary"):
                        if not smtp_user or not smtp_password:
                            st.error("请先在上方配置SMTP邮箱信息")
                        elif dry_run:
                            with st.spinner("演练预览中..."):
                                result = send_bulk_emails(
                                    smtp_user=smtp_user, smtp_password=smtp_password,
                                    email_list=email_list_for_send, sender_name=sender_name,
                                    delay_seconds=delay_seconds, dry_run=True,
                                    global_attachments=eg_global_attachments,
                                    global_cc=eg_g_cc, global_bcc=eg_g_bcc,
                                )
                            summary = [f"共 {result['total']} 封邮件待发送"]
                            if eg_g_cc: summary.append(f"抄送×{len(eg_g_cc)}")
                            if eg_g_bcc: summary.append(f"密抄×{len(eg_g_bcc)}")
                            st.success("演练完成！" + "，".join(summary))
                            rows = [{
                                "#": r["index"], "姓名": r.get("name", ""), "邮箱": r["email"],
                                "主题": r.get("subject", ""), "状态": "✅ 演练通过", "说明": r.get("message", ""),
                            } for r in result["results"]]
                            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                                         column_config={"#": st.column_config.NumberColumn(width="small")})
                        else:
                            progress = st.progress(0, text=f"准备发送 0 / {len(email_list_for_send)}")
                            status_text = st.empty()
                            results_log_container = st.container()
                            success_count = 0
                            fail_count = 0
                            detailed_rows = []

                            for i, item in enumerate(email_list_for_send):
                                status_text.write(f"📤 发货通知发送中 [{i+1}/{len(email_list_for_send)}] {item['name']} <{item['email']}> ...")
                                single_result = {"status": "error", "success_count": 0, "failed_count": 0, "results": []}
                                try:
                                    single_result = send_bulk_emails(
                                        smtp_user=smtp_user, smtp_password=smtp_password,
                                        email_list=[item], sender_name=sender_name,
                                        dry_run=False, delay_seconds=0,
                                        global_attachments=eg_global_attachments,
                                        global_cc=eg_g_cc, global_bcc=eg_g_bcc,
                                    )
                                except Exception as outer_e:
                                    single_result = {"status": "error", "success_count": 0, "failed_count": 1,
                                                     "results": [{"status": "error", "message": f"未捕获异常：{outer_e}"}]}
                                if single_result.get("success_count", 0) > 0:
                                    success_count += 1
                                    status_txt = "成功"
                                    note = ""
                                    rr = single_result.get("results", [])
                                    if rr and rr[0].get("elapsed_seconds"):
                                        note = f"耗时 {rr[0]['elapsed_seconds']}s"
                                        if rr[0].get("attempts", 1) > 1:
                                            note += f"（重试{rr[0]['attempts']-1}次）"
                                else:
                                    fail_count += 1
                                    status_txt = "失败"
                                    rr = single_result.get("results", [])
                                    if rr:
                                        note = rr[0].get("message", str(single_result))
                                    else:
                                        note = single_result.get("message", "未知错误")
                                detailed_rows.append({
                                    "#": i + 1, "姓名": item.get("name", ""), "邮箱": item["email"],
                                    "主题": item.get("subject", ""),
                                    "状态": status_txt, "详情": note,
                                })
                                progress.progress((i + 1) / len(email_list_for_send),
                                                  text=f"已发送 {i+1} / {len(email_list_for_send)}　成功 {success_count}　失败 {fail_count}")
                                if i < len(email_list_for_send) - 1 and delay_seconds > 0:
                                    import time
                                    time.sleep(delay_seconds)

                            status_text.empty()
                            summary = [f"成功 {success_count} 封，失败 {fail_count} 封（共 {len(email_list_for_send)} 封）"]
                            if eg_g_cc: summary.append(f"抄送×{len(eg_g_cc)}")
                            if eg_g_bcc: summary.append(f"密抄×{len(eg_g_bcc)}")
                            if fail_count == 0:
                                st.success("✅ 全部发送完成！" + "，".join(summary))
                            elif success_count > 0:
                                st.warning("⚠️ 部分发送完成 — " + "，".join(summary))
                            else:
                                st.error("❌ 发送全部失败 — " + "，".join(summary))

                            with results_log_container:
                                st.subheader("📋 发送详情（全部）")
                                st.dataframe(pd.DataFrame(detailed_rows), use_container_width=True, hide_index=True,
                                             column_config={
                                                 "#": st.column_config.NumberColumn(width="small"),
                                                 "状态": st.column_config.TextColumn(width="small"),
                                             })

                            st.session_state["last_send_result"] = {
                                "total": len(email_list_for_send),
                                "success": success_count,
                                "failed": fail_count,
                                "cc_count": len(eg_g_cc),
                                "bcc_count": len(eg_g_bcc),
                                "rows": detailed_rows,
                                "time": now_cn().strftime("%Y-%m-%d %H:%M:%S"),
                            }
                elif not recipient_emails.strip():
                    st.warning("请填写收件人邮箱列表")

            except Exception as e:
                st.error(f"处理过程中发生错误：\n\n{str(e)}")
                import traceback
                with st.expander("查看详细错误信息"):
                    st.code(traceback.format_exc())


def _extract_surname(name: str) -> str:
    """从姓名中提取姓氏，不管名字里是否有英文，都只提取中文姓。"""
    if not name:
        return ""
    import re
    # 去除首尾空白和常见标点
    name = name.strip().strip("·•・-_.")
    if not name:
        return ""

    # 复姓列表
    surname_map = [
        "欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟",
        "闻人", "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政",
        "濮阳", "公冶", "太叔", "申屠", "公孙", "慕容", "仲孙", "钟离", "长孙",
        "宇文", "司徒", "鲜于", "司空", "闾丘", "子车", "亓官", "司寇", "巫马",
        "公西", "颛孙", "壤驷", "公良", "漆雕", "乐正", "宰父", "谷梁", "拓跋",
        "夹谷", "轩辕", "令狐", "段干", "百里", "呼延", "东郭", "南门", "羊舌",
        "微生", "公户", "公玉", "公仪", "梁丘", "公仲", "公上", "公门", "公山",
        "公坚", "左丘", "公伯", "西门", "公祖", "第五", "公乘", "贯丘", "公皙",
        "南荣", "东里", "东宫", "仲长", "子书", "子桑", "即墨", "达奚", "褚师"
    ]

    # 提取所有中文字符部分
    chinese_parts = re.findall(r'[\u4e00-\u9fff]+', name)

    if chinese_parts:
        # 有中文字符：用第一段中文匹配复姓或取第一个字
        chinese_name = chinese_parts[0]
        for compound in surname_map:
            if chinese_name.startswith(compound):
                return compound
        return chinese_name[0] if chinese_name else ""

    # 纯英文名：取最后一个单词作为姓（Family Name）
    # 例如 "John Smith" → "Smith"，"Li Heng" → "Heng"
    # 如果是 "heng.li" 格式，取点后面的部分
    cleaned = re.sub(r'[·•・\-_.]', ' ', name)
    words = cleaned.split()
    if len(words) >= 2:
        return words[-1]  # 最后一个词是姓
    elif words:
        return words[0]  # 只有一个词，取首词
    return ""


# 中文变量名（含别名） → 实际字段名
_CN_TEMPLATE_ALIASES = {
    "姓氏": "surname", "姓": "surname", "Surname": "surname",
    "姓名": "name", "客户姓名": "name", "客户": "name",
    "名字": "given_name", "名": "given_name",
    "邮箱": "email", "Email": "email", "email": "email",
}
# 方括号占位符归一化：[xxx] 翻译成 {{yyy}} 标准语法
_BRACKET_NORMALIZE = [
    # 「客户姓名/老师」 特殊匹配：整个 [客户姓名/老师] → {{姓氏}}老师
    (r'\[\s*客户姓名\s*/\s*老师\s*\]', '{{姓氏}}老师'),
    (r'\[\s*姓名\s*/\s*老师\s*\]', '{{姓氏}}老师'),
    (r'\[\s*客户姓名\s*\+\s*老师\s*\]', '{{姓氏}}老师'),
    # 其他方括号包裹变量：[xxx] → {{xxx}}
    (r'\[\s*([^\[\]]{1,30}?)\s*\]', r'{{\1}}'),
]


def _normalize_bracket_placeholders(text: str) -> str:
    """把常见方括号占位符 [客户姓名/老师]、[姓名] 等归一化到 {{...}} 语法。"""
    if not text:
        return text
    import re
    for pattern, repl in _BRACKET_NORMALIZE:
        text = re.sub(pattern, repl, text)
    return text


def _render_template_with_cn(text: str, variables: dict) -> str:
    """用变量字典渲染模板，自动处理中文别名和方括号占位符。"""
    if not text:
        return text
    import re
    # 1. 方括号 → {{xxx}}
    text = _normalize_bracket_placeholders(text)
    # 2. 构造完整替换字典
    resolved = {}
    for k, v in variables.items():
        resolved[str(k)] = "" if v is None else str(v)
    for alias, real_key in _CN_TEMPLATE_ALIASES.items():
        if alias not in resolved and real_key in resolved:
            resolved[alias] = resolved[real_key]
    # 3. 替换 {{xxx}}
    def _repl(m):
        key = m.group(1).strip()
        # 别名解析
        real = _CN_TEMPLATE_ALIASES.get(key, key)
        if real in resolved:
            return resolved[real]
        if key in resolved:
            return resolved[key]
        return m.group(0)
    return re.sub(r'\{\{\s*([^{}]+?)\s*\}\}', _repl, text)


def show_draft_box():
    """草稿箱页面：查看/编辑/删除/定时发送草稿"""
    from modules.draft_store import list_drafts, load_draft, delete_draft, save_draft, update_draft_status

    st.title("💾 草稿箱")
    st.markdown("管理已保存的邮件草稿，支持编辑、定时发送、删除。")

    drafts = list_drafts()

    if not drafts:
        st.info("📭 草稿箱为空。请在「邮件群发」页面保存草稿后回到这里查看。")
        st.caption("💡 在邮件群发页面 → 「💾 草稿箱」expander → 输入名称 → 保存为草稿")
        return

    st.success(f"📂 共有 {len(drafts)} 个草稿")

    for d in drafts:
        status_icon = "⏰" if d.get("status") == "scheduled" else ("✅" if d.get("status") == "sent" else "📝")
        status_label = {"draft": "草稿", "scheduled": "已排期", "sent": "已发送"}.get(d.get("status", "draft"), "草稿")

        with st.expander(f"{status_icon} {d.get('name', '未命名')} — {status_label} — {d.get('updated_at', '')[:16]}"):
            # 草稿信息
            info_col1, info_col2 = st.columns(2)
            with info_col1:
                st.markdown(f"**主题模板：** {d.get('subject_template', '（无）')[:60]}")
                st.markdown(f"**发件邮箱：** {d.get('sender_email', '（未设置）')}")
                st.markdown(f"**创建时间：** {d.get('created_at', '')}")
            with info_col2:
                st.markdown(f"**定时发送：** {d.get('scheduled_time', '无')}")
                if d.get("batch_size", 0) > 0:
                    st.markdown(f"**分批：** 每批{d['batch_size']}人，间隔{d.get('batch_interval', 0)}分钟")
                st.markdown(f"**HTML格式：** {'是' if d.get('use_html') else '否'}（字号{d.get('font_size', 14)}px）")

            st.text_area("正文模板", value=d.get("body_template", ""), height=150,
                         key=f"draft_body_{d['id']}", disabled=True)

            st.markdown(f"**抄送：** {d.get('cc', '无')}　|　**密抄：** {d.get('bcc', '无')}")

            # 操作按钮
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if st.button("📤 加载到邮件群发", key=f"draft_load_{d['id']}"):
                    st.session_state["mb_subject"] = d.get("subject_template", "")
                    st.session_state["mb_body"] = d.get("body_template", "")
                    st.session_state["mb_cc_text"] = d.get("cc", "")
                    st.session_state["mb_bcc_text"] = d.get("bcc", "")
                    st.session_state["selected_main"] = "📨 邮件群发"
                    st.success("已加载！正在跳转到邮件群发页面...")
                    st.rerun()
            with btn_col2:
                if st.button("⏰ 标记为已排期", key=f"draft_sched_{d['id']}"):
                    update_draft_status(d["id"], "scheduled")
                    st.success(f"草稿「{d.get('name')}」已标记为已排期")
                    st.rerun()
            with btn_col3:
                if st.button("🗑️ 删除", key=f"draft_del_{d['id']}"):
                    delete_draft(d["id"])
                    st.rerun()


def show_email_blast():
    from modules.email_sender import test_smtp_connection, send_bulk_emails, guess_smtp_config, list_smtp_candidates

    # 定时发送：每 20 秒自动 rerun 一次以触发 tick()
    enable_auto_tick_refresh(20)

    st.title("📨 邮件群发")

    st.markdown(textwrap.dedent(
        """
    **使用说明：**
    1. 上传Excel文件（须包含「姓名」和「邮箱」列）
    2. 输入邮件主题和正文，支持模板变量：{{姓氏}} {{姓名}} {{名字}} {{邮箱}} 以及Excel中的任意列名
    3. 演练预览确认后，一键批量发送
    """))

    with st.expander("🔐 SMTP邮箱配置", expanded=True):
        # 多发件邮箱保存与切换
        if "saved_senders" not in st.session_state:
            st.session_state["saved_senders"] = []
        saved = st.session_state["saved_senders"]

        if len(saved) > 0:
            sender_col1, sender_col2 = st.columns([3, 1])
            with sender_col1:
                sender_options = ["（直接输入）"] + [f"{s['name']} ({s['user']})" for s in saved]
                selected_idx = st.selectbox("🏷️ 选择发件邮箱", range(len(sender_options)),
                                           format_func=lambda i: sender_options[i], key="mb_sender_select")
            with sender_col2:
                if selected_idx > 0 and st.button("🗑️ 删除此邮箱", key="mb_del_sender"):
                    del saved[selected_idx - 1]
                    st.session_state["saved_senders"] = saved
                    st.rerun()
        else:
            selected_idx = 0

        # 如果选中了已保存的邮箱，自动填充
        if selected_idx > 0 and selected_idx <= len(saved):
            s = saved[selected_idx - 1]
            default_user = s["user"]
            default_password = s["password"]
            default_name = s["name"]
            default_host = s.get("host", "")
            default_port = s.get("port", "")
            default_ssl = s.get("ssl", True)
        else:
            default_user = st.session_state.get("email_smtp_user", "1392039316@qq.com")
            default_password = st.session_state.get("email_smtp_password", "dtepljmsauzgjbfa")
            default_name = st.session_state.get("email_sender_name", "Cindy 张茹")
            default_host = st.session_state.get("mb_smtp_host", "")
            default_port = st.session_state.get("mb_smtp_port", "")
            default_ssl = st.session_state.get("mb_smtp_ssl", True)

        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            smtp_user = st.text_input("邮箱地址", value=default_user, key="mb_smtp_user")
        with cfg_col2:
            smtp_password = st.text_input("SMTP授权码", type="password", value=default_password, key="mb_smtp_password")
        with cfg_col3:
            sender_name = st.text_input("发件人名称", value=default_name, key="mb_sender_name")

        # 保存当前邮箱配置
        save_col1, save_col2 = st.columns(2)
        with save_col1:
            if st.button("💾 保存当前邮箱配置", key="mb_save_sender"):
                exists = False
                for s in saved:
                    if s["user"] == smtp_user:
                        s["password"] = smtp_password
                        s["name"] = sender_name
                        s["host"] = st.session_state.get("mb_manual_host", "")
                        s["port"] = st.session_state.get("mb_manual_port", "")
                        s["ssl"] = st.session_state.get("mb_manual_ssl", True)
                        exists = True
                        break
                if not exists and smtp_user:
                    saved.append({"user": smtp_user, "password": smtp_password, "name": sender_name,
                                  "host": st.session_state.get("mb_manual_host", ""),
                                  "port": st.session_state.get("mb_manual_port", ""),
                                  "ssl": st.session_state.get("mb_manual_ssl", True)})
                st.session_state["saved_senders"] = saved
                st.success(f"已保存「{sender_name}」({smtp_user})，共 {len(saved)} 个邮箱配置")
        with save_col2:
            if st.button("📋 查看已保存邮箱", key="mb_list_senders"):
                if saved:
                    st.write(pd.DataFrame([{"邮箱": s["user"], "名称": s["name"]} for s in saved]), use_container_width=True)
                else:
                    st.info("还没有保存的邮箱配置")

        if smtp_user:
            host, port, ssl_flag = guess_smtp_config(smtp_user)
            st.caption(f"自动识别SMTP: {host}:{port} {'(SSL)' if ssl_flag else '(STARTTLS)'}")

        with st.expander("🛠️ 高级：手动覆盖SMTP服务器", expanded=False):
            override_col1, override_col2, override_col3 = st.columns(3)
            with override_col1:
                manual_host = st.text_input("SMTP主机（留空用自动识别）", value=default_host, key="mb_manual_host", placeholder="例如 smtp.qiye.163.com")
            with override_col2:
                manual_port_input = st.text_input("端口（留空用自动识别）", value=str(default_port or ""), key="mb_manual_port", placeholder="例如 465")
            with override_col3:
                manual_ssl = st.checkbox("使用SSL（465/994）", value=default_ssl, key="mb_manual_ssl")
            candidates = list_smtp_candidates(smtp_user) if smtp_user else []
            if len(candidates) > 1:
                st.caption("常见候选（企业域名不确定时可尝试）：" + "；".join([f"{c[3]} {c[0]}:{c[1]}" for c in candidates[1:]]))

        eff_host = manual_host.strip() or host
        try:
            eff_port = int(str(manual_port_input).strip()) if str(manual_port_input).strip() else port
        except Exception:
            eff_port = port
        eff_ssl = manual_ssl

        if st.button("🔌 测试连接", key="mb_test_conn"):
            with st.spinner("测试SMTP连接..."):
                conn_result = test_smtp_connection(smtp_user, smtp_password, eff_host, eff_port)
                if conn_result["status"] == "success":
                    st.success(f"✅ 连接成功！{conn_result['smtp_host']}:{conn_result['smtp_port']} ({conn_result['elapsed_seconds']}s)")
                else:
                    st.error(f"❌ 连接失败: {conn_result.get('message', '未知错误')}")
                    candidates = list_smtp_candidates(smtp_user)
                    if len(candidates) > 1:
                        st.info(f"💡 自动识别未命中，请在「高级」里手动指定。常见候选：" + "；".join([f"{c[3]} {c[0]}:{c[1]}" for c in candidates[1:]]))

        st.session_state["email_smtp_user"] = smtp_user
        st.session_state["email_smtp_password"] = smtp_password
        st.session_state["email_sender_name"] = sender_name
        st.session_state["mb_smtp_host"] = manual_host
        st.session_state["mb_smtp_port"] = str(manual_port_input or "")
        st.session_state["mb_smtp_ssl"] = manual_ssl
        st.session_state["mb_smtp_eff_host"] = eff_host
        st.session_state["mb_smtp_eff_port"] = eff_port
        st.session_state["mb_smtp_eff_ssl"] = eff_ssl

    st.subheader("1. 上传Excel")
    uploaded_file = st.file_uploader("选择Excel文件", type=["xlsx", "xls"], key="mb_excel")

    recipients_data = []
    if uploaded_file is not None:
        with st.spinner("正在读取Excel文件..."):
            try:
                df = pd.read_excel(uploaded_file)
                # ===== 防御：去掉重复列名 + 强制所有单元格为标量（避免merged cell/公式返回Series） =====
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = ["_".join([str(c) for c in col if str(c) != ""]).strip("_") for col in df.columns.values]
                df.columns = [str(c).strip() for c in df.columns]
                # 重名列去重（保留首次出现）
                seen_cols = {}
                keep_idx = []
                for i, col in enumerate(df.columns):
                    if col not in seen_cols:
                        seen_cols[col] = True
                        keep_idx.append(i)
                df = df.iloc[:, keep_idx].copy()
                # 强制转标量字符串
                for col in df.columns:
                    try:
                        df[col] = df[col].apply(lambda v: (v.item() if hasattr(v, "item") and not isinstance(v, str)
                                                              else v) if pd.notna(v) else v)
                    except Exception:
                        pass
                st.success(f"读取成功！共 {len(df)} 行数据，列：{', '.join(df.columns)}")

                name_col = None
                email_col = None
                for col in df.columns:
                    col_lower = str(col).lower()
                    # 模糊匹配姓名列：列名中含有「姓名/客户/联系人/名称」或英文 name/customer/contact
                    if (any(kw in col for kw in ("姓名", "客户", "联系人", "名称", "客户姓名")) or
                        any(kw in col_lower for kw in ("name", "customer", "contact"))):
                        if name_col is None:
                            name_col = col
                    # 邮箱模糊匹配：列名含「邮箱/邮件」或 email
                    if (col in ("邮箱", "邮件", "email", "e-mail", "mail") or
                        any(kw in col_lower for kw in ["email", "邮箱", "邮件"])):
                        if email_col is None:
                            email_col = col
                # 如果还是没找到姓名列， fallback：取第一列
                if name_col is None and len(df.columns) > 0:
                    name_col = df.columns[0]
                # 如果还是没找到邮箱列， fallback：取第二列
                if email_col is None and len(df.columns) > 1:
                    email_col = df.columns[1]

                st.info(f"姓名字段：{name_col or '（未找到）'}　｜　邮箱字段：{email_col or '（未找到）'}")
                # 手动选择列（让用户能覆盖自动识别）
                col_override1, col_override2 = st.columns(2)
                with col_override1:
                    name_col = st.selectbox(
                        "📝 确认姓名字段", df.columns.tolist(),
                        index=df.columns.tolist().index(name_col) if name_col in df.columns.tolist() else 0,
                        key="mb_name_col",
                    )
                with col_override2:
                    email_col = st.selectbox(
                        "📧 确认邮箱字段", df.columns.tolist(),
                        index=df.columns.tolist().index(email_col) if email_col in df.columns.tolist() else 0,
                        key="mb_email_col",
                    )

                recipients_data = []
                for _, row in df.iterrows():
                    raw_name = row.get(name_col) if name_col else ""
                    raw_email = row.get(email_col) if email_col else ""

                    # 清洗姓名
                    if pd.isna(raw_name):
                        raw_name = ""
                    name = str(raw_name).strip()
                    if name.lower() in ("nan", "none", ""):
                        name = ""

                    # 清洗邮箱
                    if pd.isna(raw_email):
                        raw_email = ""
                    email = str(raw_email).strip().replace(" ", "").replace("\u3000", "")
                    if email.lower() in ("nan", "none", ""):
                        email = ""

                    if email:
                        entry = {"email": email, "name": name}
                        entry["surname"] = _extract_surname(name)
                        entry["given_name"] = name[len(entry["surname"]):] if name and entry["surname"] else name
                        for col in df.columns:
                            val = row[col]
                            if pd.notna(val):
                                entry[str(col)] = str(val).strip()
                            else:
                                entry[str(col)] = ""
                        recipients_data.append(entry)

                if recipients_data:
                    preview_cols = [c for c in ["name", "email", "surname", "given_name"] if c in recipients_data[0]]

                    # ===== 收件人可编辑表格（支持删除行+手动新增） =====
                    df_editable = pd.DataFrame(
                        [{k: r.get(k, "") for k in preview_cols} for r in recipients_data]
                    )
                    df_editable.insert(0, "勾选发送", True)
                    df_editable.insert(1, "序号", range(1, len(df_editable) + 1))

                    with st.expander(f"📋 查看/编辑全部 {len(df_editable)} 条收件人数据（支持增删）", expanded=True):
                        # 顶部：手动新增收件人
                        st.markdown("**➕ 手动新增收件人**")
                        add_col1, add_col2, add_col3 = st.columns([3, 3, 1])
                        with add_col1:
                            add_name = st.text_input("姓名", key="mb_add_name", placeholder="如：张三")
                        with add_col2:
                            add_email = st.text_input("邮箱", key="mb_add_email", placeholder="如：zhangsan@example.com")
                        with add_col3:
                            if st.button("➕ 添加", key="mb_add_row"):
                                if add_email.strip():
                                    new_entry = {
                                        "email": add_email.strip(),
                                        "name": add_name.strip(),
                                        "surname": _extract_surname(add_name.strip()),
                                    }
                                    new_entry["given_name"] = (add_name.strip()[len(new_entry["surname"]):]
                                                              if add_name.strip() and new_entry["surname"] else add_name.strip())
                                    recipients_data.append(new_entry)
                                    st.success(f"✅ 已添加：{new_entry['name'] or '-'} <{new_entry['email']}>")
                                    st.rerun()
                                else:
                                    st.warning("请先填写邮箱")

                        st.markdown("**📝 收件人列表编辑（勾选列=是否发送，姓名/邮箱双击可改，点击列首可排序筛选）**")

                        # 用 AgGrid 可编辑 + 选中行删除
                        gb = GridOptionsBuilder.from_dataframe(df_editable)
                        gb.configure_default_column(editable=True, resizable=True)
                        gb.configure_column("勾选发送", editable=True, width=90,
                                            cellEditor="agCheckboxCellEditor")
                        gb.configure_column("序号", editable=False, width=70, pinned=True)
                        gb.configure_column("name", header_name="姓名", width=140)
                        gb.configure_column("email", header_name="邮箱", width=260)
                        gb.configure_column("surname", header_name="姓", width=70)
                        gb.configure_column("given_name", header_name="名字", width=100)
                        gb.configure_selection(selection_mode="multiple", use_checkbox=False)
                        grid_response = AgGrid(
                            df_editable,
                            gridOptions=gb.build(),
                            update_mode=GridUpdateMode.MODEL_CHANGED,
                            data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                            fit_columns_on_grid_load=True,
                            height=min(500, 80 + len(df_editable) * 35),
                            theme="streamlit",
                            key="mb_recipients_grid",
                        )

                        # ===== 强类型防御：AgGrid 不同版本返回值不一样（dict / DataFrame / 自定义对象） =====
                        new_df = df_editable.copy()
                        selected_rows = []
                        if isinstance(grid_response, dict):
                            try:
                                grid_raw = grid_response.get("data")
                                if isinstance(grid_raw, pd.DataFrame):
                                    new_df = grid_raw.copy()
                                elif isinstance(grid_raw, list):
                                    if grid_raw and all(isinstance(x, dict) for x in grid_raw):
                                        new_df = pd.DataFrame(grid_raw)
                                    # else: grid_raw 是 list[str] 之类，保持 fallback
                                elif grid_raw is not None:
                                    try:
                                        candidate = pd.DataFrame(grid_raw)
                                        if not candidate.empty:
                                            new_df = candidate
                                    except Exception:
                                        pass
                            except Exception:
                                new_df = df_editable.copy()

                            # 安全读取 selected_rows，无论 .get() 返回什么，只保留 list[dict]
                            try:
                                sel = grid_response.get("selected_rows")
                                if sel is None:
                                    selected_rows = []
                                elif isinstance(sel, list):
                                    selected_rows = [r for r in sel if isinstance(r, dict)]
                                # 如果是 DataFrame / Series：转 dict list
                                elif isinstance(sel, pd.DataFrame):
                                    selected_rows = sel.to_dict(orient="records")
                            except Exception:
                                selected_rows = []

                        if len(selected_rows) > 0 and st.button(f"🗑️ 删除选中的 {len(selected_rows)} 行", key="mb_del_selected"):
                            selected_emails = []
                            for r in selected_rows:
                                if not isinstance(r, dict):
                                    continue
                                val = r.get("email")
                                if val is None:
                                    continue
                                selected_emails.append(str(val).strip())
                            before = len(recipients_data)
                            recipients_data = [
                                r for r in recipients_data
                                if isinstance(r, dict) and str(r.get("email", "")).strip() not in selected_emails
                            ]
                            removed = before - len(recipients_data)
                            st.success(f"✅ 已删除 {removed} 条")
                            st.rerun()

                        # 把编辑后的姓名/邮箱同步回 recipients_data，并按"勾选发送"过滤
                        updated_count = 0
                        enabled_indices = set()
                        email_to_edited = {}
                        # 按邮箱作为关联键，把表格编辑后的值同步回 recipients_data
                        if isinstance(new_df, pd.DataFrame) and "email" in new_df.columns and "name" in new_df.columns:
                            for _, row in new_df.iterrows():
                                e = str(row.get("email", "")).strip()
                                if not e:
                                    continue
                                raw_checked = row.get("勾选发送", True)
                                # 防御：raw_checked 可能是 numpy.bool_ / str / int
                                if isinstance(raw_checked, str):
                                    if raw_checked.strip() == "":
                                        checked = True
                                    else:
                                        checked = raw_checked.strip().lower() in ("true", "1", "yes", "on")
                                else:
                                    try:
                                        checked = bool(raw_checked)
                                    except Exception:
                                        checked = True
                                email_to_edited[e] = {
                                    "name": str(row.get("name", "")).strip(),
                                    "checked": checked,
                                }
                            for r in recipients_data:
                                if not isinstance(r, dict):
                                    continue
                                e = str(r.get("email", "")).strip()
                                if e in email_to_edited:
                                    new_name = email_to_edited[e]["name"]
                                    if new_name and new_name != str(r.get("name", "")).strip():
                                        r["name"] = new_name
                                        r["surname"] = _extract_surname(new_name)
                                        r["given_name"] = (new_name[len(r["surname"]):]
                                                          if new_name and r["surname"] else new_name)
                                        updated_count += 1
                                    if email_to_edited[e]["checked"]:
                                        enabled_indices.add(id(r))

                        # 过滤：只保留被勾选中的（如果用户动了勾选列）
                        if email_to_edited and any(not v["checked"] for v in email_to_edited.values()):
                            recipients_data = [r for r in recipients_data if id(r) in enabled_indices]

                        st.caption(f"共 {len(recipients_data)} 条数据　|　编辑同步：{updated_count} 条姓名已更新　|　将发送：{len(recipients_data)} 封")
                else:
                    st.warning("未找到有效收件人，请确认Excel包含邮箱列")

            except Exception as e:
                st.error(f"读取失败: {e}")
                import traceback
                with st.expander("详细错误"):
                    st.code(traceback.format_exc())

    st.divider()
    st.subheader("2. 编辑邮件内容")

    subject_template = st.text_input(
        "邮件主题",
        value=st.session_state.get("mb_subject", "尊敬的{{姓氏}}老师，您好"),
        key="mb_subject",
    )

    body_template = st.text_area(
        "邮件正文",
        value=st.session_state.get("mb_body", "尊敬的{{姓氏}}老师：\n\n您好！\n\n（在此编写邮件内容，支持{{姓氏}} {{姓名}}等变量）\n\n祝好！"),
        key="mb_body",
        height=250,
    )

    if "{{" in subject_template or "{{" in body_template:
        st.caption("💡 可用变量: {{姓氏}} {{姓名}} {{名字}} {{邮箱}} 以及Excel中的任意列名")

    # ===== 讯飞星火AI 助手 =====
    with st.expander("🤖 星火AI助手（润色/改写）", expanded=False):
        st.caption("接入讯飞星火Spark Lite，可对邮件正文进行智能润色、改写")
        ai_col1, ai_col2 = st.columns([1, 2])
        with ai_col1:
            ai_action = st.selectbox("操作", ["润色优化", "改写正文", "生成主题建议"],
                                     key="mb_ai_action")
        with ai_col2:
            if ai_action == "改写正文":
                ai_instruction = st.text_input("改写指令", value="更简短",
                                                key="mb_ai_instruction",
                                                placeholder="如：更正式、更简短、更亲切")
            elif ai_action == "生成主题建议":
                ai_topic = st.text_input("邮件内容/关键词", value="",
                                         key="mb_ai_topic",
                                         placeholder="如：新品发布通知")
        if st.button("✨ 执行AI", key="mb_ai_run", type="primary"):
            try:
                from modules.spark_ai import polish_email, rewrite_email, generate_email_subject
                with st.spinner("星火AI思考中..."):
                    if ai_action == "润色优化":
                        result = polish_email(body_template)
                        st.session_state["mb_body"] = result
                        st.text_area("润色结果", value=result, height=200, key="mb_ai_result")
                        st.success("✅ 润色完成！点击下方「应用结果」按钮更新正文")
                        if st.button("📝 应用结果到正文", key="mb_ai_apply"):
                            st.session_state["mb_body"] = result
                            st.rerun()
                    elif ai_action == "改写正文":
                        result = rewrite_email(body_template, ai_instruction)
                        st.session_state["mb_body"] = result
                        st.text_area("改写结果", value=result, height=200, key="mb_ai_result2")
                        st.success("✅ 改写完成！点击下方「应用结果」按钮更新正文")
                        if st.button("📝 应用结果到正文", key="mb_ai_apply2"):
                            st.session_state["mb_body"] = result
                            st.rerun()
                    elif ai_action == "生成主题建议":
                        result = generate_email_subject(ai_topic)
                        st.info("主题建议：\n" + result)
            except Exception as e:
                st.error(f"AI助手出错: {e}")
                with st.expander("详细错误"):
                    st.code(traceback.format_exc())

    # ===== 富文本格式刷（选中文字加粗/调色/改字号） =====
    with st.expander("🎨 富文本格式刷（选中文字单独设置样式）", expanded=False):
        st.caption("在下方输入要单独设置格式的文字片段，选择样式后，系统会生成带样式的HTML标签插入到正文中")
        rt_col1, rt_col2, rt_col3, rt_col4 = st.columns(4)
        with rt_col1:
            rt_text = st.text_input("要格式化的文字", key="mb_rt_text", placeholder="如：限时优惠")
        with rt_col2:
            rt_bold = st.checkbox("加粗", value=True, key="mb_rt_bold")
        with rt_col3:
            rt_color = st.color_picker("文字颜色", value="#FF0000", key="mb_rt_color")
        with rt_col4:
            rt_size = st.number_input("字号(px)", min_value=10, max_value=48, value=18, step=1, key="mb_rt_size")
        rt_col_bg1, rt_col_bg2 = st.columns([1, 4])
        with rt_col_bg1:
            rt_enable_bg = st.checkbox("添加背景色", value=False, key="mb_rt_enable_bg")
        with rt_col_bg2:
            rt_bg = st.color_picker("背景色", value="#FFFACD", key="mb_rt_bg")
        if st.button("📋 生成带样式片段", key="mb_rt_gen") and rt_text:
            style_parts = []
            if rt_bold:
                style_parts.append("font-weight:bold")
            style_parts.append(f"color:{rt_color}")
            style_parts.append(f"font-size:{rt_size}px")
            if rt_enable_bg:
                style_parts.append(f"background-color:{rt_bg}")
            styled = f'<span style="{";".join(style_parts)}">{rt_text}</span>'
            st.code(styled, language="html")
            st.caption("复制上方代码，粘贴到正文中（需勾选「以HTML富文本格式发送」）")
            # 直接插入到正文末尾
            if st.button("➕ 插入到正文末尾", key="mb_rt_insert"):
                st.session_state["mb_body"] = body_template + "\n" + styled
                st.success("已插入！")
                st.rerun()

    # 字体大小/颜色/样式控制（全局）
    with st.expander("🎨 全局字体与样式设置", expanded=False):
        font_col1, font_col2, font_col3, font_col4 = st.columns(4)
        with font_col1:
            font_size = st.number_input("字体大小(px)", min_value=10, max_value=32, value=14, step=1, key="mb_font_size")
        with font_col2:
            font_color = st.color_picker("字体颜色", value="#333333", key="mb_font_color")
        with font_col3:
            bg_color = st.color_picker("背景颜色", value="#ffffff", key="mb_bg_color")
        with font_col4:
            font_family = st.selectbox("字体", ["微软雅黑", "宋体", "黑体", "Arial", "Times New Roman", "仿宋"],
                                       index=0, key="mb_font_family")
        use_html = st.checkbox("🎨 以HTML富文本格式发送（支持字体大小/颜色）", value=False, key="mb_use_html")
        if use_html:
            st.caption("✅ 启用后邮件将以 HTML 格式发送，收件人将看到带字体样式的排版")
        else:
            st.caption("当前为纯文本发送，字体设置不生效（需要勾选上方选项）")

    st.divider()
    st.subheader("3. 预览与发送")

    col1, col2 = st.columns([1, 3])
    with col1:
        delay_seconds = st.number_input("发送间隔(秒)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="mb_delay")
        dry_run = st.checkbox("演练模式（不实际发送）", value=True, key="mb_dry_run")
        with st.expander("👥 抄送 / 密抄", expanded=False):
            global_cc_text = st.text_area(
                "抄送 CC（出现在邮件头，收件人可见）",
                value=st.session_state.get("mb_cc_text", ""),
                key="mb_cc_input",
                height=55,
                placeholder="每行一个，或用逗号分隔\n例如：cindy.zhang@ibiologistics.com",
            )
            global_bcc_text = st.text_area(
                "密抄 BCC（不出现在邮件头，收件人不可见）",
                value=st.session_state.get("mb_bcc_text", ""),
                key="mb_bcc_input",
                height=55,
                placeholder="每行一个，或用逗号分隔\n例如：boss@ibiologistics.com，可用来备份自己",
            )
            st.session_state["mb_cc_text"] = global_cc_text
            st.session_state["mb_bcc_text"] = global_bcc_text
        with st.expander("⏰ 定时发送 / 分批发送", expanded=False):
            enable_schedule = st.checkbox("启用定时发送", value=False, key="mb_enable_schedule")
            enable_batch = False
            scheduled_time = None
            batch_size = 0
            batch_interval = 0
            if enable_schedule:
                from datetime import datetime as _dt, timedelta as _td
                # ⚠️ 所有默认值/比较统一用北京时间（Streamlit Cloud 在 UTC）
                cn_now = now_cn()
                min_date = cn_now.date()
                default_date = cn_now.date()
                # 🔍 调试：显示北京时间，防止时区导致的8小时误解
                st.caption(f"🕐 当前系统识别的北京时间：**{cn_now.strftime('%Y-%m-%d %H:%M')}**（如果不对，请立刻刷新页面清理缓存）")
                sched_date = st.date_input("发送日期", value=default_date, min_value=min_date, key="mb_sched_date")
                default_t = (cn_now + _td(minutes=10)).time()
                sched_time = st.time_input("发送时间", value=default_t, key="mb_sched_time")
                scheduled_time = _dt.combine(sched_date, sched_time)

                # ========== 关键修复：防误设 + 自动顺延 ==========
                wait_now = (scheduled_time - cn_now).total_seconds()
                if wait_now < 0 and wait_now > -60:
                    pass
                elif wait_now < 0:
                    scheduled_time = scheduled_time + _timedelta(days=1)
                    sched_date = scheduled_time.date()
                    st.warning(f"ℹ️ 所选今日 {sched_time} 已过（北京已到 {cn_now.strftime('%H:%M')}），自动顺延为明日 {scheduled_time.strftime('%m-%d %H:%M')}")
                    wait_now = (scheduled_time - cn_now).total_seconds()

                # ===== 可视化倒计时：显示"距发送 X 天 Y 小时 Z 分" =====
                wait_abs = int(abs(wait_now))
                w_days, rem = divmod(wait_abs, 86400)
                w_hours, w_mins = divmod(rem // 60, 60)
                if wait_now >= 0:
                    delta_msg = f"📅 距发送：{'%d天 ' % w_days if w_days else ''}{w_hours:02d}小时{w_mins:02d}分钟"
                    st.success(delta_msg)
                # 超长预警：避免用户误设到下个月
                if wait_now >= 7 * 86400:
                    st.error("⚠️ 发送时间在 7 天之后。请确认「发送日期」没有误选到下个月？如果日期正确请忽略。")

                st.caption(f"将在 {scheduled_time.strftime('%Y-%m-%d %H:%M')} 自动开始发送（请保持页面打开，每 20 秒自动检查一次）")

                # 分批定时发送
                st.markdown("---")
                enable_batch = st.checkbox("🔄 启用分批发送（大量收件人时推荐）", value=False, key="mb_enable_batch")
                if enable_batch:
                    batch_col1, batch_col2 = st.columns(2)
                    with batch_col1:
                        batch_size = st.number_input("每批数量", min_value=1, max_value=500, value=10, step=1, key="mb_batch_size")
                    with batch_col2:
                        batch_interval = st.number_input("每批间隔（分钟）", min_value=1, max_value=1440, value=30, step=5, key="mb_batch_interval")
                    total_recipients = len(recipients_data) if recipients_data else 0
                    if total_recipients > 0:
                        num_batches = (total_recipients + batch_size - 1) // batch_size
                        st.info(f"📊 共 {total_recipients} 人，分 {num_batches} 批，每批 {batch_size} 人，间隔 {batch_interval} 分钟")
                        st.caption(f"第一批 {scheduled_time.strftime('%H:%M')} 发送，最后一批约 {(scheduled_time + _td(minutes=batch_interval * (num_batches - 1))).strftime('%H:%M')} 发送")
                else:
                    batch_size = 0
                    batch_interval = 0
            else:
                st.caption("当前为立即发送模式（点击按钮立即开始发送）")

        # ===== 草稿箱快捷保存 =====
        with st.expander("💾 草稿箱", expanded=False):
            from modules.draft_store import save_draft, list_drafts, load_draft, delete_draft
            draft_col1, draft_col2 = st.columns([2, 1])
            with draft_col1:
                draft_name = st.text_input("草稿名称", value="", key="mb_draft_name", placeholder="如：9月新品通知")
            with draft_col2:
                if st.button("💾 保存为草稿", key="mb_save_draft"):
                    draft_data = {
                        "name": draft_name or f"草稿_{now_cn().strftime('%m-%d %H:%M')}",
                        "subject_template": subject_template,
                        "body_template": body_template,
                        "sender_email": st.session_state.get("email_smtp_user", ""),
                        "sender_password": st.session_state.get("email_smtp_password", ""),
                        "sender_name": st.session_state.get("email_sender_name", ""),
                        "cc": st.session_state.get("mb_cc_text", ""),
                        "bcc": st.session_state.get("mb_bcc_text", ""),
                        "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S") if scheduled_time else None,
                        "batch_size": batch_size,
                        "batch_interval": batch_interval,
                        "font_size": st.session_state.get("mb_font_size", 14),
                        "font_color": st.session_state.get("mb_font_color", "#333333"),
                        "use_html": st.session_state.get("mb_use_html", False),
                        "status": "draft",
                    }
                    did = save_draft(draft_data)
                    st.success(f"✅ 草稿已保存：{draft_data['name']}（ID: {did}）")

            # 列出已保存草稿
            existing_drafts = list_drafts()
            if existing_drafts:
                st.markdown("---")
                st.caption(f"已有 {len(existing_drafts)} 个草稿")
                for d in existing_drafts[:10]:
                    d_col1, d_col2, d_col3 = st.columns([3, 1, 1])
                    with d_col1:
                        status_icon = "⏰" if d.get("status") == "scheduled" else ("✅" if d.get("status") == "sent" else "📝")
                        st.text(f"{status_icon} {d.get('name', '未命名')} ({d.get('updated_at', '')[:16]})")
                    with d_col2:
                        if st.button("📂 加载", key=f"mb_load_draft_{d['id']}"):
                            loaded = load_draft(d["id"])
                            if loaded:
                                st.session_state["mb_subject"] = loaded.get("subject_template", "")
                                st.session_state["mb_body"] = loaded.get("body_template", "")
                                st.session_state["mb_cc_text"] = loaded.get("cc", "")
                                st.session_state["mb_bcc_text"] = loaded.get("bcc", "")
                                st.success(f"已加载草稿：{loaded.get('name', '')}")
                                st.rerun()
                    with d_col3:
                        if st.button("🗑️", key=f"mb_del_draft_{d['id']}"):
                            delete_draft(d["id"])
                            st.rerun()
    with col2:
        attachment_files = st.file_uploader(
            "📎 添加附件（每封邮件都会带上，支持多文件）",
            type=None, accept_multiple_files=True, key="mb_attachments",
            help="支持 PDF / Excel / Word / 图片 / ZIP 等任意格式。中文文件名不会乱码。"
        )
        if attachment_files:
            total_kb = sum(f.size for f in attachment_files) / 1024
            st.caption(f"已选 {len(attachment_files)} 个附件，共 {total_kb:.1f} KB：" +
                       "、".join([f.name for f in attachment_files]))

    if recipients_data and (subject_template or body_template):
        email_list_all = []
        for r in recipients_data:
            # 使用统一模板渲染（自动兼容方括号 [客户姓名/老师] 和中文别名）
            subject = _render_template_with_cn(subject_template, r)
            body = _render_template_with_cn(body_template, r)
            email_list_all.append({
                "email": r["email"],
                "name": r.get("name", ""),
                "subject": subject,
                "body": body,
            })

        missing_vars = set()
        import re
        for item in email_list_all:
            remaining = re.findall(r'\{\{([^}]+)\}\}', item["subject"] + item["body"])
            missing_vars.update(remaining)
        if missing_vars:
            st.warning(f"⚠️ 模板中存在未替换的变量: {', '.join(missing_vars)}")

        # 如果启用 HTML，把纯文本 body 包装成带样式的 HTML
        if use_html:
            def _wrap_html(text_body):
                # 把换行转成 <br>，制表符转成 &nbsp;&nbsp;
                import html as _html_mod
                safe = _html_mod.escape(text_body)
                safe = safe.replace("\n", "<br>\n")
                style = (f"font-size:{font_size}px;color:{font_color};"
                         f"background-color:{bg_color};font-family:{font_family};"
                         f"line-height:1.8;padding:16px;")
                return f'<div style="{style}">{safe}</div>'
            for item in email_list_all:
                item["body"] = _wrap_html(item["body"])
                item["is_html"] = True
        else:
            for item in email_list_all:
                item["is_html"] = False

        # ===== 步骤A：为每封邮件分配绝对下标（= email_list_all 的 index），作为所有匹配的唯一锚点 =====
        email_list_all_with_idx = [{"_abs_idx": i, **item} for i, item in enumerate(email_list_all)]

        # ===== 发送范围选择（先切范围，得到候选绝对下标集合） =====
        send_qty_col1, send_qty_col2 = st.columns([1, 2])
        with send_qty_col1:
            send_mode = st.radio("📊 发送范围", ["全部发送", "前N封", "指定范围"], index=0, key="mb_send_mode")
        with send_qty_col2:
            if send_mode == "前N封":
                send_n = st.number_input("发送前几封", min_value=1, max_value=len(email_list_all),
                                         value=min(10, len(email_list_all)), step=1, key="mb_send_n")
                cand_abs_idx = list(range(min(send_n, len(email_list_all))))
            elif send_mode == "指定范围":
                range_col1, range_col2 = st.columns(2)
                with range_col1:
                    start_idx = st.number_input("起始序号(从1开始)", min_value=1, max_value=len(email_list_all),
                                                value=1, step=1, key="mb_range_start")
                with range_col2:
                    end_idx = st.number_input("结束序号", min_value=int(start_idx), max_value=len(email_list_all),
                                              value=min(int(start_idx) + 9, len(email_list_all)), step=1, key="mb_range_end")
                cand_abs_idx = list(range(int(start_idx)-1, int(end_idx)))
            else:
                cand_abs_idx = list(range(len(email_list_all)))

        # ===== 单封邮件勾选（是否发送）—— 只在"发送范围候选"范围内显示，用绝对下标 =====
        st.markdown("#### ☑️ 单封邮件是否发送")
        per_mail_toggle = st.checkbox("启用单封选择（取消勾选的邮件不会发送）", value=False, key="mb_per_mail_toggle")
        if per_mail_toggle:
            send_flags = st.session_state.setdefault("mb_send_flags", {})
            for abs_i in cand_abs_idx:
                item = email_list_all[abs_i]
                key = f"mb_mail_flag_{abs_i}"
                send_flags[abs_i] = st.checkbox(
                    f"发送　第 {abs_i+1} 封（{item.get('name') or '-'} <{item.get('email','')}>）｜{item.get('subject','')[:60]}",
                    value=send_flags.get(abs_i, True),
                    key=key,
                )
            st.session_state["mb_send_flags"] = send_flags
            selected_abs_idx = [i for i in cand_abs_idx if send_flags.get(i, True)]
            st.caption(f"☑️ 已勾选 {len(selected_abs_idx)} / 候选 {len(cand_abs_idx)}（全量 {len(email_list_all)}）封")
        else:
            selected_abs_idx = list(cand_abs_idx)

        # ===== 汇总 email_list_for_send（用绝对下标从 email_list_all 取） =====
        # 注意：单封编辑会直接 in-place 修改 email_list_all[abs_i] 里的 subject/body/email
        # 所以这里最后再取值，确保所有编辑都生效
        email_list_for_send = [dict(email_list_all[i]) for i in selected_abs_idx if 0 <= i < len(email_list_all)]

        # 把 Streamlit UploadedFile 转成 (bytes, filename) 列表供后端附加
        global_attachments = None
        if attachment_files:
            global_attachments = []
            for uf in attachment_files:
                uf.seek(0)
                global_attachments.append((uf.read(), uf.name))

        # 全局 Cc / Bcc（前端文案里提到的密抄就在这里）
        from modules.email_sender import _normalize_addrs
        g_cc = _normalize_addrs(global_cc_text)
        g_bcc = _normalize_addrs(global_bcc_text)

        info_parts = [f"待发送 {len(email_list_for_send)} 封邮件（共 {len(email_list_all)} 封）"]
        if send_mode != "全部发送":
            info_parts.append(f"已选范围")
        if global_attachments:
            info_parts.append(f"每封附加 {len(global_attachments)} 个文件")
        if g_cc:
            info_parts.append(f"抄送 CC×{len(g_cc)}")
        if g_bcc:
            info_parts.append(f"密抄 BCC×{len(g_bcc)}")
        if use_html:
            info_parts.append(f"HTML富文本({font_size}px)")
        if enable_schedule and scheduled_time:
            info_parts.append(f"定时 {scheduled_time.strftime('%H:%M')}")
        if enable_batch and batch_size > 0:
            num_batches = (len(email_list_for_send) + batch_size - 1) // batch_size
            info_parts.append(f"分{num_batches}批×{batch_size}人/间隔{batch_interval}分钟")
        st.info("，".join(info_parts))
        if g_cc or g_bcc:
            st.caption("  · ".join([
                (f"CC：{', '.join(g_cc)}" if g_cc else ""),
                (f"BCC：{', '.join(g_bcc)}" if g_bcc else ""),
            ] if (g_cc and g_bcc) else ([(f"CC：{', '.join(g_cc)}" if g_cc else f"BCC：{', '.join(g_bcc)}")])))

        # 预览数量选择
        preview_col_p, preview_col_s, preview_col_e = st.columns([1, 1.2, 1.5])
        with preview_col_p:
            preview_options = [("全部", len(email_list_for_send))]
            for n in [3, 10, 50]:
                if len(email_list_for_send) > n:
                    preview_options.append((f"前 {n} 封", n))
            preview_labels = [o[0] for o in preview_options]
            preview_values = [o[1] for o in preview_options]
            default_idx = 0  # 默认选"全部"
            preview_limit_label = st.selectbox(
                "📧 预览数量",
                range(len(preview_options)),
                format_func=lambda i: preview_labels[i],
                index=default_idx, key="mb_preview_limit",
            )
            preview_limit = preview_values[preview_limit_label]
        with preview_col_s:
            preview_show_body = st.checkbox("显示正文摘要", value=True, key="mb_show_body")
        with preview_col_e:
            enable_edit = st.checkbox("✏️ 允许单封编辑", value=False, key="mb_enable_edit")

        n_preview = len(selected_abs_idx) if preview_limit >= len(selected_abs_idx) else preview_limit
        preview_abs_idx = selected_abs_idx[:n_preview]
        with st.expander(f"📧 预览前 {n_preview} 封（共 {len(selected_abs_idx)} 封）", expanded=True):
            for local_pos, abs_i in enumerate(preview_abs_idx):
                # 引用 email_list_all 的原始对象，所有 in-place 修改都能保留
                item = email_list_all[abs_i]
                disp_no = abs_i + 1  # 显示"原始全量列表里的第几封"，和上方单封勾选面板里的序号完全一致
                line1 = f"**[{disp_no}] {item['name']}** ({item['email']})　•　主题：{item['subject']}"
                extras = []
                if g_cc: extras.append("👁️ CC：" + "、".join(g_cc))
                if g_bcc: extras.append("🕵️ BCC：" + "、".join(g_bcc))
                if global_attachments:
                    names = [a[1] for a in global_attachments] if isinstance(global_attachments[0], tuple) else [str(a) for a in global_attachments]
                    extras.append("📎 " + "、".join(names))

                if enable_edit:
                    # 单封编辑模式：用 abs_i 作唯一 key，直接改 email_list_all[abs_i]
                    with st.expander(f"✏️ [{disp_no}] {item['name']} ({item['email']})", expanded=False):
                        edit_col1, edit_col2 = st.columns([2, 1])
                        with edit_col1:
                            new_subject = st.text_input(f"主题", value=item["subject"], key=f"mb_edit_subject_{abs_i}")
                        with edit_col2:
                            new_email = st.text_input(f"收件人", value=item["email"], key=f"mb_edit_email_{abs_i}")
                        new_body = st.text_area(f"正文", value=item["body"], key=f"mb_edit_body_{abs_i}", height=150)
                        if st.button("💾 保存修改", key=f"mb_save_{abs_i}"):
                            email_list_all[abs_i]["subject"] = new_subject
                            email_list_all[abs_i]["body"] = new_body
                            email_list_all[abs_i]["email"] = new_email
                            # 改了收件人姓名吗？单封编辑里现在不改 name，name 是 recipients_data 里的，也同步一下
                            st.success(f"✅ 已保存 第{disp_no}封 <{item.get('name','')}> 的修改")
                            st.rerun()
                        st.caption("　".join(extras))
                else:
                    if preview_show_body:
                        body_excerpt = item['body'][:400] + ("..." if len(item['body']) > 400 else "")
                        st.markdown(line1 + ("　　" if extras else ""))
                        if extras: st.caption("　".join(extras))
                        if use_html:
                            st.markdown(body_excerpt, unsafe_allow_html=True)
                        else:
                            st.text(body_excerpt)
                    else:
                        st.markdown(line1)
                        if extras: st.caption("　".join(extras))
                st.divider()

        # 定时发送等待提示
        send_button_label = "演练预览" if dry_run else "立即发送"
        if enable_schedule and scheduled_time and not dry_run:
            from datetime import datetime as _dt2
            wait_seconds = (scheduled_time - _dt2.now()).total_seconds()
            if wait_seconds > 0:
                send_button_label = f"⏰ 定时发送 ({scheduled_time.strftime('%m-%d %H:%M')})"

        if st.button("🚀 " + send_button_label, key="mb_send", type="primary"):
            if not smtp_user or not smtp_password:
                st.error("请先在上方配置SMTP邮箱信息")
            else:
                # ★ 发送前再构建 email_list_for_send，用最新的 email_list_all（包含所有单封编辑修改）
                email_list_for_send = []
                send_abs_indices = []
                for i in selected_abs_idx:
                    if 0 <= i < len(email_list_all):
                        email_list_for_send.append(dict(email_list_all[i]))
                        send_abs_indices.append(i)

                if dry_run:
                    with st.spinner("演练预览中..."):
                        result = send_bulk_emails(
                            smtp_user=smtp_user, smtp_password=smtp_password,
                            email_list=email_list_for_send, sender_name=sender_name,
                            delay_seconds=delay_seconds, dry_run=True,
                            global_attachments=global_attachments,
                            global_cc=g_cc, global_bcc=g_bcc,
                            is_html=use_html,
                        )
                    summary = [f"共 {result['total']} 封邮件"]
                    if g_cc: summary.append(f"抄送×{len(g_cc)}")
                    if g_bcc: summary.append(f"密抄×{len(g_bcc)}")
                    st.success("演练完成！" + "，".join(summary))
                    rows = [{
                        "#": send_abs_indices[r["index"]-1] + 1 if r.get("index") and 1 <= r["index"] <= len(send_abs_indices) else send_abs_indices[k] + 1
                        if False else (send_abs_indices[k] + 1 if k < len(send_abs_indices) else r.get("index","?"))
                        for k, r in enumerate(result["results"])
                    }] if False else None
                    rows = []
                    for k, r in enumerate(result["results"]):
                        rows.append({
                            "#": send_abs_indices[k] + 1 if k < len(send_abs_indices) else (r.get("index","?")),
                            "姓名": r.get("name", ""),
                            "邮箱": r["email"],
                            "主题": r.get("subject", ""),
                            "状态": "✅ 演练通过",
                            "详情": r.get("message", ""),
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                                 column_config={"#": st.column_config.NumberColumn(width="small")})
                else:
                    # ==============================================================
                    # ✨ 实际发送 · 分两条路径：
                    #   A) 立即发送（未启用定时）→ 老的同步方案：st.progress + status_text
                    #      在当前请求里逐封发送 → 丝滑实时更新（用户喜欢的"最初样子"）
                    #
                    #   B) 启用定时/分批定时 → 新的 JSONL + 后台线程 + 5秒刷新
                    # ==============================================================
                    if not enable_schedule:
                        # ---------------- 路径A：立即发送 · 同步丝滑实时进度 ----------------
                        progress = st.progress(0.0, text=f"0 / {len(email_list_for_send)}")
                        status_text = st.empty()
                        detail_placeholder = st.container()
                        success_count = 0; fail_count = 0
                        detailed_rows = []

                        for idx, item in enumerate(email_list_for_send):
                            abs_no = selected_abs_idx[idx] + 1 if idx < len(selected_abs_idx) else idx + 1
                            status_text.info(f"📤 发送中 [{abs_no}] {item.get('name','')} <{item['email']}> ...")
                            result = {"status": "error", "success_count": 0, "failed_count": 0, "results": []}
                            try:
                                result = send_bulk_emails(
                                    smtp_user=smtp_user, smtp_password=smtp_password,
                                    email_list=[item], sender_name=sender_name,
                                    delay_seconds=0, dry_run=False,
                                    global_attachments=global_attachments,
                                    global_cc=g_cc, global_bcc=g_bcc,
                                    is_html=use_html,
                                )
                            except Exception as oe:
                                result = {"status":"error","success_count":0,"failed_count":1,
                                          "results":[{"status":"error","message":f"{type(oe).__name__}: {oe}"}]}
                            if result.get("success_count", 0) > 0:
                                success_count += 1; status_txt = "✅ 成功"
                                note = ""
                                rr = result.get("results", [])
                                if rr and rr[0].get("elapsed_seconds"):
                                    note = f"耗时 {rr[0]['elapsed_seconds']}s"
                                    if rr[0].get("attempts",1) > 1: note += f"（重试{rr[0]['attempts']-1}次）"
                            else:
                                fail_count += 1; status_txt = "❌ 失败"
                                rr = result.get("results", [])
                                if rr:
                                    note = str(rr[0].get("message") or rr[0].get("error") or str(result))[:300]
                                else:
                                    note = str(result.get("message","未知错误"))[:300]
                            detailed_rows.append({
                                "#": abs_no, "姓名": item.get("name",""),
                                "邮箱": item["email"], "主题": item.get("subject",""),
                                "状态": status_txt, "详情": note,
                            })
                            progress.progress((idx+1)/len(email_list_for_send),
                                              text=f"{idx+1}/{len(email_list_for_send)}　✅ {success_count} 成功 / ❌ {fail_count} 失败")
                            if idx < len(email_list_for_send)-1 and delay_seconds > 0:
                                time.sleep(delay_seconds)

                        status_text.empty()
                        summary = [f"成功 {success_count} 封，失败 {fail_count} 封（共 {len(email_list_for_send)} 封）"]
                        if g_cc: summary.append(f"抄送×{len(g_cc)}")
                        if g_bcc: summary.append(f"密抄×{len(g_bcc)}")
                        if fail_count == 0:
                            st.success("✅ 全部发送完成！" + "，".join(summary))
                        elif success_count > 0:
                            st.warning("⚠️ 部分发送完成 — " + "，".join(summary))
                        else:
                            st.error("❌ 发送全部失败 — " + "，".join(summary))
                        st.markdown("### 📋 发送详情（全部）")
                        st.dataframe(pd.DataFrame(detailed_rows), use_container_width=True, hide_index=True)
                        st.session_state["last_blast_result"] = {
                            "total": len(email_list_for_send),
                            "success": success_count, "failed": fail_count,
                            "cc_count": len(g_cc), "bcc_count": len(g_bcc),
                            "rows": detailed_rows,
                            "time": now_cn().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        # 顺便把结果也作为一个"done 状态的 job"记到任务列表，方便历史追溯
                        import uuid as _uuid
                        hist_job = {
                            "id": "job_hist_" + _uuid.uuid4().hex[:10],
                            "scheduled_at": now_cn().isoformat(),
                            "status": "done" if fail_count == 0 else ("partial" if success_count > 0 else "failed"),
                            "created_at": now_cn().isoformat(),
                            "started_at": now_cn().isoformat(),
                            "finished_at": now_cn().isoformat(),
                            "smtp_user": smtp_user, "sender_name": sender_name,
                            "total": len(email_list_for_send),
                            "success_count": success_count, "fail_count": fail_count,
                            "sent_list": [
                                {
                                    "index": r["#"], "status": "success" if "成功" in str(r["状态"]) else "failed",
                                    "name": r["姓名"], "email": r["邮箱"],
                                    "subject": r["主题"], "note": r["详情"],
                                } for r in detailed_rows
                            ],
                            "enable_batch": False, "batch_size": 0, "batch_interval": 0,
                            "delay_seconds": delay_seconds,
                            "mode": "instant_sync",
                        }
                        _SCHED_SENDER.upsert(hist_job)
                    else:
                        # ---------------- 路径B：定时/分批定时 · JSONL后台线程 + 5s刷新 ----------------
                        import uuid
                        att_refs = []
                        for a in (global_attachments or []):
                            if isinstance(a, tuple) and len(a) >= 2:
                                data_bytes, name = a[0], str(a[1])
                            else:
                                data_bytes = a
                                name = "attachment"
                            b64 = None
                            if isinstance(data_bytes, str) and os.path.isfile(data_bytes):
                                with open(data_bytes, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode("ascii")
                            elif isinstance(data_bytes, (bytes, bytearray)):
                                b64 = base64.b64encode(bytes(data_bytes)).decode("ascii")
                            elif hasattr(data_bytes, "read"):
                                try:
                                    data_bytes.seek(0)
                                    b64 = base64.b64encode(data_bytes.read()).decode("ascii")
                                except Exception: pass
                            if b64:
                                att_refs.append([name, b64])

                        job = {
                            "id": "job_" + uuid.uuid4().hex[:12],
                            "scheduled_at": scheduled_time.isoformat(),
                            "status": "pending",
                            "created_at": now_cn().isoformat(),
                            "smtp_user": smtp_user,
                            "smtp_password": smtp_password,
                            "sender_name": sender_name,
                            "email_list": email_list_for_send,
                            "delay_seconds": delay_seconds,
                            "global_attachments_refs": att_refs,
                            "global_cc": g_cc,
                            "global_bcc": g_bcc,
                            "is_html": use_html,
                            "enable_batch": bool(enable_batch and batch_size > 0),
                            "batch_size": int(batch_size or 0),
                            "batch_interval": int(batch_interval or 0),
                            "total": len(email_list_for_send),
                        }
                        _SCHED_SENDER.upsert(job)
                        _SCHED_SENDER.tick()

                        if enable_schedule and scheduled_time:
                            wait_now = (scheduled_time - now_cn()).total_seconds()
                            if wait_now > 0:
                                wd, rem = divmod(int(wait_now), 86400)
                                wh, wm = divmod(rem // 60, 60)
                                st.success(
                                    f"✅ 已登记定时任务！\n\n"
                                    f"· 任务ID：`{job['id']}`\n"
                                    f"· 发送时间：**{scheduled_time.strftime('%Y-%m-%d %H:%M')}**\n"
                                    f"· 还有：{'%d天 ' % wd if wd else ''}{wh:02d}小时{wm:02d}分钟\n"
                                    f"· 邮件数量：{len(email_list_for_send)} 封\n"
                                    f"\n📌 **请保持此页面打开**（每 5 秒自动刷新一次，到点自动开始发送）。"
                                )
                            else:
                                st.success(f"✅ 已登记发送任务，正在后台发送中... ID: `{job['id']}`。每 5 秒自动刷新进度。")
                        else:
                            st.success(f"✅ 已登记发送任务，正在后台发送中... ID: `{job['id']}`。每 5 秒自动刷新进度。")
                        st.caption("💡 下方实时进度面板 & 「📅 已排期的定时任务列表」可查看实时状态")

                        # ---- 这里才显示内嵌的实时进度面板 ----
                        st.markdown("#### 📊 实时发送进度")
                        cur_job = None
                        for j in _SCHED_SENDER.list_jobs():
                            if j.get("id") == job["id"]:
                                cur_job = j; break
                        if cur_job is None:
                            st.info("等待调度中…")
                        else:
                            total = int(cur_job.get("total") or 0)
                            sent_list = cur_job.get("sent_list") or []
                            succ_list = [s for s in sent_list if str(s.get("status","")).lower() in ("success","成功","ok","done")]
                            fail_list = [s for s in sent_list if s not in succ_list]
                            n_sent = len(sent_list)
                            cur_idx = int(cur_job.get("current_index") or 0)
                            status = cur_job.get("status") or "pending"

                            if total > 0:
                                pct = max(0.0, min(1.0, n_sent / total))
                                st.progress(pct, text=f"{n_sent}/{total}　（✅ {len(succ_list)} 成功 / ❌ {len(fail_list)} 失败）")
                            else:
                                st.progress(0.0, text="0/0")

                            if status == "running":
                                cur_name = str(cur_job.get("current_name") or "")
                                cur_email = str(cur_job.get("current_email") or "")
                                cur_subj = str(cur_job.get("current_subject") or "")
                                started_at = cur_job.get("started_at")
                                elapsed = ""
                                if started_at:
                                    try:
                                        sec = int((now_cn() - datetime.fromisoformat(started_at)).total_seconds())
                                        mm, ss = divmod(sec, 60)
                                        elapsed = f"（已用 {mm}:{ss:02d}）"
                                    except Exception: pass
                                if cur_idx > 0:
                                    st.info(
                                        f"🚀 **当前正在发送第 {cur_idx}/{total} 封** {elapsed}\n\n"
                                        f"· 👤 {cur_name}　📧 `{cur_email}`\n\n"
                                        f"· 🏷️ {cur_subj[:90]}{'…' if len(cur_subj) > 90 else ''}"
                                    )
                            elif status in ("pending","scheduled"):
                                sat = cur_job.get("scheduled_at")
                                try:
                                    wait = (datetime.fromisoformat(sat) - now_cn()).total_seconds()
                                    if wait > 0:
                                        wd, rem = divmod(int(wait), 86400); wh, wm = divmod(rem//60, 60)
                                        st.info(f"⏳ 等待定时触发：还有 {'%d天 '%wd if wd else ''}{wh:02d}:{wm:02d}（{sat[:16]} 开始）")
                                    else:
                                        st.info("⏳ 即将开始发送…")
                                except Exception:
                                    st.info("⏳ 等待调度中…")
                            elif status == "done":
                                st.success(f"✅ 全部发送完成：成功 {len(succ_list)} / 失败 {len(fail_list)} / 共 {total}")
                            elif status == "partial":
                                st.warning(f"⚠️ 部分完成：成功 {len(succ_list)} / 失败 {len(fail_list)} / 共 {total}")
                            elif status == "failed":
                                st.error(f"❌ 发送失败：{str(cur_job.get('error','未知错误'))[:200]}")
                            elif status == "cancelled":
                                st.warning("🚫 用户取消")
                            elif status == "expired":
                                st.warning(f"⌛ 过期未触发：{str(cur_job.get('error',''))[:200]}")

                            if sent_list:
                                with st.expander(f"✅ 已发送明细（{len(sent_list)} 封）", expanded=False):
                                    rows = []
                                    for s in sent_list:
                                        icon = "✅" if str(s.get("status","")).lower() in ("success","成功","ok","done") else "❌"
                                        msg = str(s.get("note") or s.get("message") or s.get("error") or "")
                                        if len(msg) > 200: msg = msg[:200] + "…"
                                        rows.append({
                                            "#": s.get("index","-"),
                                            "状态": f"{icon} {s.get('status','')}",
                                            "姓名": s.get("name",""),
                                            "邮箱": s.get("email",""),
                                            "主题": (str(s.get("subject",""))[:50] + ("…" if len(str(s.get("subject","")))>50 else "")),
                                            "耗时/原因": msg,
                                        })
                                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                        # 手动刷新按钮（不等5秒）
                        if st.button("🔄 立刻刷新进度", key="mb_refresh_progress_now"):
                            _SCHED_SENDER.tick()
                            st.rerun()

        # =========================================================
        # 任务列表：展示所有排期/已完成任务（草稿任务也一并在这里看到）
        # =========================================================
        st.divider()
        st.markdown("### 📅 已排期的发送任务列表")
        jobs = _SCHED_SENDER.list_jobs()
        jobs_sorted = sorted(jobs, key=lambda j: j.get("scheduled_at", ""), reverse=True)
        if not jobs_sorted:
            st.caption("暂无排期任务。填好参数后点「🚀 发送」按钮就会出现在这里。")
        else:
            show_rows = []
            for j in jobs_sorted[:50]:
                status = j.get("status") or "pending"
                icon = {
                    "pending": "⏳", "scheduled": "⏳", "running": "🚀",
                    "done": "✅", "failed": "❌", "partial": "⚠️",
                    "cancelled": "🚫", "expired": "⌛",
                }.get(status, "❓")
                try:
                    st_at = datetime.fromisoformat(j["scheduled_at"])
                    st_at_str = st_at.strftime("%m-%d %H:%M")
                    if status in ("pending", "scheduled"):
                        wait = (st_at - now_cn()).total_seconds()
                        if wait > 0:
                            wd, rem = divmod(int(wait), 86400)
                            wh, wm = divmod(rem // 60, 60)
                            eta_str = f"（还有{'%d天' % wd if wd else ''}{wh:02d}:{wm:02d}）"
                        elif wait < -300:
                            eta_str = f"（⚠️ 过期{int(-wait//60)}分钟，未触发）"
                        else:
                            eta_str = "（即将发送）"
                    else:
                        eta_str = ""
                except Exception:
                    st_at_str = str(j.get("scheduled_at", "-"))
                    eta_str = ""
                total = int(j.get("total") or 0)
                succ = int(j.get("success_count") or 0)
                fail = int(j.get("fail_count") or 0)
                detail = ""
                if status in ("done", "failed", "partial"):
                    detail = f" · {succ}成功/{fail}失败/共{total}"
                elif status == "running":
                    detail = f" · 共{total}封 · 发送中..."
                elif status == "pending":
                    detail = f" · 待发送 {total} 封"
                elif status == "expired":
                    detail = " · " + (j.get("error") or "")
                err_txt = f" · {j['error'][:80]}" if j.get("error") and status in ("failed",) else ""
                show_rows.append({
                    "状态": f"{icon} {status}",
                    "发送时间": f"{st_at_str}{eta_str}",
                    "收件人": f"{total}封" + detail + err_txt,
                    "ID": j["id"],
                })
            st.dataframe(pd.DataFrame(show_rows), use_container_width=True, hide_index=True)
            st.caption("💡 列表每 20 秒自动刷新。取消仍未发送的任务请在下方输入任务 ID：")
            col_cancel1, col_cancel2 = st.columns([3, 1])
            with col_cancel1:
                cancel_id = st.text_input("输入要取消的任务 ID", key="mb_cancel_job_id", placeholder="如 job_abcdef123456")
            with col_cancel2:
                if st.button("🚫 取消任务", key="mb_do_cancel_job"):
                    if cancel_id:
                        _SCHED_SENDER.cancel(cancel_id.strip())
                        st.success(f"已取消任务 {cancel_id}（如果已在发送则无法停止当前邮件）")
                        st.rerun()
                    else:
                        st.warning("请先输入任务 ID")
    elif not recipients_data:
        st.info("请先上传Excel文件")
    else:
        st.info("请填写邮件主题和正文")


def show_inventory():
    from modules.inventory.ui import show_inventory_page

    try:
        db = get_db_manager()
        show_inventory_page(db, operator=st.session_state.get("username", ""))
    except Exception as exc:
        st.error(f"库存页面加载失败：{exc}")
        st.info("请刷新页面重试，或联系管理员。")


def show_user_management(config):
    st.title("👑 用户管理")
    
    st.markdown(textwrap.dedent(
        """
    **功能说明：**
    管理员可以查看所有用户信息、登录状态和域名信息。
    """))
    
    st.subheader("📊 当前域名")
    try:
        domain = st.secrets.get("domain", "customer-points-system.streamlit.app")
    except Exception:
        domain = "customer-points-system.streamlit.app"
    st.info(f"当前域名：{domain}")
    
    st.subheader("👥 用户列表")
    
    users_data = []
    for username, info in config['credentials']['usernames'].items():
        is_logged_in = st.session_state.get('username') == username
        users_data.append({
            "用户名": username,
            "姓名": info.get('name', ''),
            "邮箱": info.get('email', ''),
            "角色": info.get('role', 'user'),
            "登录状态": "✅ 在线" if is_logged_in else "❌ 离线"
        })
    
    if users_data:
        users_df = pd.DataFrame(users_data)
        st.dataframe(users_df, use_container_width=True)
        
        st.subheader("📈 用户统计")
        col1, col2, col3 = st.columns(3)
        col1.metric("总用户数", len(users_data))
        col2.metric("管理员数", len([u for u in users_data if u['角色'] == 'admin']))
        col3.metric("在线用户", len([u for u in users_data if u['登录状态'] == '✅ 在线']))
    else:
        st.warning("暂无用户数据")


def show_invoice_registration():
    st.title("🧾 红冲发票自动登记")
    
    st.markdown(textwrap.dedent(
        """
    **功能说明：**
    通过IMAP连接邮箱，自动检索发票邮件，下载PDF发票并按规则命名保存到本地目录。
    """))
    
    config = {
        "imap_server": st.text_input("IMAP服务器", "imap.qiye.163.com"),
        "imap_port": st.number_input("IMAP端口", min_value=1, max_value=65535, value=993),
        "email": st.text_input("邮箱地址", "huiyin.guo@ibiologistics.com"),
        "password": st.text_input("客户端授权码", type="password"),
        "sender": st.text_input("发件人过滤", "百旺金穗云dzfpfwpt@hnfapiao.com"),
        "subject_filter": st.text_input("主题关键字", "开具的发票"),
        "output_dir": st.text_input("保存目录", os.path.join(_WRITABLE_DIR, "发票汇总")),
        "days_back": st.number_input("检索天数", min_value=1, max_value=30, value=5),
    }
    
    dry_run = st.checkbox("试运行（不实际下载）", value=False)

    if st.button("开始下载发票", key="btn-fetch-invoices", type="primary"):
        db_manager = get_db_manager()
        invoice_fetcher = InvoiceFetcher(config, db_manager=db_manager)

        errors = invoice_fetcher.validate_config()
        if errors:
            for error in errors:
                st.error(error)
            return

        with st.spinner("正在连接邮箱并下载发票..."):
            results, summary = invoice_fetcher.fetch_invoices(days=config["days_back"], dry_run=dry_run)

        if results is None:
            st.error(summary)
            return

        st.success(f"处理完成！共处理 {summary['total_processed']} 封邮件，成功 {summary['success_count']} 封，失败 {summary['failed_count']} 封")

        st.subheader(f"📂 保存目录: {summary['output_dir']}")

        success_results = [r for r in results if r["status"] == "success"]
        failed_results = [r for r in results if r["status"] == "failed"]

        if success_results:
            st.subheader("✅ 成功下载的发票")
            success_df = pd.DataFrame(success_results)
            success_df = success_df[["date", "buyer", "amount", "filename", "source", "folder"]]
            st.dataframe(success_df, use_container_width=True)

        if failed_results:
            st.subheader("❌ 失败的邮件")
            failed_df = pd.DataFrame(failed_results)
            failed_df = failed_df[["date", "subject", "folder", "reason"]]
            st.dataframe(failed_df, use_container_width=True)

    # 历史发票记录（从数据库加载）
    try:
        db_manager = get_db_manager()
        if hasattr(db_manager, 'get_invoice_records'):
            st.header("📚 历史发票记录")

            with st.expander("查看历史发票记录", expanded=False):
                hist_col1, hist_col2 = st.columns(2)
                with hist_col1:
                    hist_status = st.selectbox("状态筛选", ["全部", "success", "failed"], key="hist_inv_status")
                with hist_col2:
                    hist_buyer = st.text_input("购方名称筛选", key="hist_inv_buyer")

                try:
                    history = db_manager.get_invoice_records(
                        status=None if hist_status == "全部" else hist_status,
                        buyer=hist_buyer if hist_buyer else None,
                        limit=100,
                    )
                    if history:
                        hist_df = pd.DataFrame(history)
                        display_cols = ["id", "invoice_date", "subject", "buyer", "amount",
                                        "status", "filename", "source"]
                        available_cols = [c for c in display_cols if c in hist_df.columns]
                        st.dataframe(hist_df[available_cols], use_container_width=True, hide_index=True)
                        st.caption(f"共 {len(history)} 条记录")
                    else:
                        st.info("暂无历史发票记录")
                except Exception as e:
                    st.warning(f"加载历史发票失败: {e}")
    except Exception:
        pass


def main():
    try:
        _main_inner()
    except Exception as e:
        st.set_page_config(page_title="启动错误", layout="wide")
        st.error(f"❌ 应用启动失败: {type(e).__name__}: {e}")
        st.subheader("诊断信息")
        st.code(traceback.format_exc(), language="python")
        with st.expander("环境信息"):
            st.text(f"Python: {sys.version}")
            st.text(f"应用目录: {_APP_DIR}")
            st.text(f"可写目录: {_WRITABLE_DIR}")
            st.text(f"Cloud模式: {_IS_CLOUD}")
            st.text(f"Config文件: {CONFIG_PATH}")
            st.text(f"DB路径: {DB_PATH}")
            st.text(f"sys.path:")
            for p in sys.path:
                st.text(f"  {p}")


def _main_inner():
    st.set_page_config(
        page_title="澄天小助手",
        page_icon="🐭",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # 配置Plotly深色主题
    try:
        px.defaults.template = "plotly_dark"
        # 设置自定义颜色
        import plotly.graph_objects as go
        go.layout.Template()
    except:
        pass
    
    from modules.theme import apply_all_styles
    apply_all_styles()

    # 登录路由下隐藏侧边栏：用 class 匹配 theme.py 的 .no-show 规则，其他路由侧边栏默认保留
    hide_sidebar_css = textwrap.dedent(
        """
        <style>
        [data-testid="stSidebar"] { display: none; }
        </style>
        """
    )
    st.markdown(hide_sidebar_css, unsafe_allow_html=True)
    
    # 加载配置（Cloud 环境使用可写路径缓存）
    _config_cache_path = os.path.join(_WRITABLE_DIR, "config.yaml")
    if os.path.exists(_config_cache_path):
        with open(_config_cache_path) as file:
            config = yaml.load(file, Loader=SafeLoader)
    elif os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as file:
            config = yaml.load(file, Loader=SafeLoader)
    else:
        st.error(f"配置文件不存在: {CONFIG_PATH}")
        st.stop()
    
    authenticator = stauth.Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )
    
    if st.session_state.get('authentication_status') != True:
        # 极简模式：theme.py 已提供 .login-container 最小居中样式（max-width 460 + margin auto），
        # 此处仅开一个简单容器 div 包裹内容，去掉科技风发光/渐变装饰。
        st.markdown('<div class="login-container">', unsafe_allow_html=True)

        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.markdown(get_logo_html(90), unsafe_allow_html=True)
        with col_title:
            st.title("澄天小助手")
            st.caption("TECH ASSISTANT SYSTEM")

        st.divider()

        login_tab, register_tab = st.tabs(["登录系统", "新用户注册"])

        with login_tab:
            authenticator.login(location="main")

        with register_tab:
            st.subheader("创建新账号")
            
            new_username = st.text_input("用户名", key="reg_username", placeholder="请输入用户名")
            new_email = st.text_input("邮箱", key="reg_email", placeholder="请输入邮箱地址")
            new_password = st.text_input("密码", type="password", key="reg_password", placeholder="至少8位字符")
            confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password", placeholder="再次输入密码")
            
            if st.button("注册新账号", key="btn_register", type="primary"):
                if not new_username or not new_email or not new_password:
                    st.error("请填写所有必填字段")
                elif new_password != confirm_password:
                    st.error("两次输入的密码不一致")
                elif new_username in config['credentials']['usernames']:
                    st.error("该用户名已存在")
                else:
                    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    config['credentials']['usernames'][new_username] = {
                        "email": new_email,
                        "name": new_username,
                        "password": hashed_password,
                        "role": "user"
                    }
                    
                    # 写入可写路径（Cloud 环境降级到 /tmp）
                    _save_path = _config_cache_path if _IS_CLOUD else CONFIG_PATH
                    try:
                        with open(_save_path, 'w') as file:
                            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
                        if _IS_CLOUD:
                            st.info(f"💡 注册信息已保存到云端临时存储（重启后需重新注册）")
                    except Exception as write_err:
                        st.warning(f"⚠️ 写入失败: {write_err}。注册信息仅在当前会话有效。")
                    
                    st.success("🎉 注册成功！请切换到登录页面登录")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.session_state.get('authentication_status') == False:
            st.error("❌ 用户名或密码错误")
            return
        
        if st.session_state.get('authentication_status') == None:
            return
    
    if st.session_state.get('authentication_status'):
        selected_main = st.session_state.get('selected_main', '🏠 首页')
        data = st.session_state.get('data')
        
        col_header_left, col_header_right = st.columns([4, 1])
        with col_header_right:
            col_btns = st.columns([1, 1])
            with col_btns[0]:
                if selected_main != '🏠 首页':
                    if st.button("← 返回首页", key="btn-back"):
                        st.session_state['selected_main'] = '🏠 首页'
                        st.rerun()
            with col_btns[1]:
                if st.button("退出登录", key="btn-logout"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
        
        if selected_main == '🏠 首页':
            show_home(config)
        elif selected_main == '📊 客户积分智能分析':
            selected_sub = st.session_state.get('selected_sub', '📈 数据概览')

            sub_options = [
                ("📈 数据概览", "数据概览"),
                ("👥 客户管理", "客户管理"),
                ("🏆 积分管理", "积分管理"),
                ("📥 数据导入", "数据导入"),
                ("📝 报表导出", "报表导出")
            ]

            sub_cols = st.columns(len(sub_options))
            for i, (icon, label) in enumerate(sub_options):
                btn_key = f"btn-sub-{label}"
                is_active = selected_sub == icon

                with sub_cols[i]:
                    if is_active:
                        if st.button(icon, key=btn_key, type="primary"):
                            st.session_state['selected_sub'] = icon
                            st.rerun()
                    else:
                        if st.button(icon, key=btn_key):
                            st.session_state['selected_sub'] = icon
                            st.rerun()

            st.divider()
            
            if selected_sub == "📈 数据概览":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_dashboard(data)
            elif selected_sub == "👥 客户管理":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_customer_management(data)
            elif selected_sub == "🏆 积分管理":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_point_management(data)
            elif selected_sub == "📥 数据导入":
                show_data_import()
            elif selected_sub == "📝 报表导出":
                if data is None:
                    data = load_data()
                    if data:
                        st.session_state['data'] = data
                show_reports(data)
        
        elif selected_main == '📧 JAX邮件生成器':
            show_email_generator()
        
        elif selected_main == '🧾 红冲发票自动登记':
            show_invoice_registration()
        
        elif selected_main == '📋 报价助手':
            show_quotation()
        
        elif selected_main == '🎬 AI 视频剪辑':
            try:
                from modules.video_editor import show_video_editor
                show_video_editor()
            except Exception as exc:
                st.error(f"视频剪辑模块加载失败：{exc}")
                st.info("请确认视频剪辑相关依赖已安装。")

        elif selected_main == '📦 库存管理':
            show_inventory()

        elif selected_main == '📨 邮件群发':
            show_email_blast()

        elif selected_main == '💾 草稿箱':
            show_draft_box()

        elif selected_main == '👑 用户管理':
            show_user_management(config)


if __name__ == "__main__":
    main()
