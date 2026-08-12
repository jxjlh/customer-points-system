"""
数据库连接诊断工具

用于检测数据库连接状态并提供详细错误信息。
在 Streamlit Cloud 上部署时，可用于快速定位连接问题。
"""
import os
import sys
from typing import Dict, Any, Optional, Callable


def diagnose_postgres_connection(
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    sslmode: str = "require",
    connect_timeout: int = 10,
) -> Dict[str, Any]:
    """
    诊断 PostgreSQL 连接状态
    
    Returns:
        dict with keys: success, message, details, error_type
    """
    result = {
        "success": False,
        "message": "",
        "details": {},
        "error_type": "",
    }

    # 检查 psycopg2 是否可用
    try:
        import psycopg2
        import psycopg2.extras
        result["details"]["psycopg2_version"] = psycopg2.__version__
    except ImportError as e:
        result["error_type"] = "IMPORT_ERROR"
        result["message"] = f"psycopg2 未安装: {e}"
        return result

    # 检查基本配置
    result["details"]["config"] = {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "sslmode": sslmode,
        "connect_timeout": connect_timeout,
    }

    # 尝试连接
    conn = None
    try:
        dsn = (
            f"host={host} port={port} dbname={dbname} "
            f"user={user} password={password} "
            f"sslmode={sslmode} connect_timeout={connect_timeout}"
        )
        result["details"]["dsn_length"] = len(dsn)
        
        conn = psycopg2.connect(dsn)
        result["details"]["connection_params"] = conn.get_dsn_parameters()
        
        # 执行简单查询
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS test")
            row = cur.fetchone()
            result["details"]["query_result"] = str(row)
            
            cur.execute("SELECT version()")
            version = cur.fetchone()
            result["details"]["server_version"] = str(version[0]) if version else "unknown"
        
        result["success"] = True
        result["message"] = "数据库连接成功！"
        
    except psycopg2.OperationalError as e:
        result["error_type"] = "OPERATIONAL_ERROR"
        result["message"] = f"连接操作错误: {str(e)}"
        result["details"]["error_code"] = str(e.pgcode) if hasattr(e, 'pgcode') else None
        result["details"]["error_detail"] = str(e.pgerror) if hasattr(e, 'pgerror') else str(e)
        # 分析常见错误
        if "timeout" in str(e).lower() or "timeout expired" in str(e).lower():
            result["details"]["possible_cause"] = "连接超时，请检查网络或防火墙设置"
        elif "password" in str(e).lower():
            result["details"]["possible_cause"] = "密码错误"
        elif "role" in str(e).lower() or "user" in str(e).lower():
            result["details"]["possible_cause"] = "用户名或角色不存在"
        elif "database" in str(e).lower():
            result["details"]["possible_cause"] = "数据库不存在"
        elif "ssl" in str(e).lower():
            result["details"]["possible_cause"] = "SSL 连接失败，请检查 sslmode 设置"
        elif "connection refused" in str(e).lower():
            result["details"]["possible_cause"] = "连接被拒绝，请检查主机和端口"
            
    except psycopg2.ProgrammingError as e:
        result["error_type"] = "PROGRAMMING_ERROR"
        result["message"] = f"编程错误: {str(e)}"
        
    except Exception as e:
        result["error_type"] = "UNKNOWN_ERROR"
        result["message"] = f"未知错误: {type(e).__name__}: {str(e)}"
        result["details"]["exception_type"] = type(e).__name__
        
    finally:
        if conn:
            try:
                conn.close()
                result["details"]["conn_closed"] = True
            except Exception:
                pass

    return result


def diagnose_streamlit_secrets() -> Dict[str, Any]:
    """
    诊断 Streamlit secrets 配置
    """
    result = {
        "success": False,
        "message": "",
        "available_sections": [],
        "postgres_config": None,
        "postgres_keys": [],
    }

    try:
        import streamlit as st
        
        if not hasattr(st, 'secrets'):
            result["message"] = "st.secrets 不可用"
            return result
            
        # 检查可用的配置节
        result["available_sections"] = list(st.secrets.keys()) if hasattr(st.secrets, 'keys') else []
        
        # 检查 postgres 配置
        if "postgres" in st.secrets:
            pg = st.secrets["postgres"]
            result["postgres_keys"] = list(pg.keys()) if hasattr(pg, 'keys') else []
            result["postgres_config"] = {
                "host": pg.get("host", ""),
                "port": pg.get("port", ""),
                "dbname": pg.get("dbname", ""),
                "user": pg.get("user", ""),
                "has_password": bool(pg.get("password", "")),
                "sslmode": pg.get("sslmode", "prefer"),
            }
            result["success"] = True
            result["message"] = "secrets 配置检查完成"
        else:
            result["message"] = "未找到 [postgres] 配置节"
            
    except Exception as e:
        result["message"] = f"检查 secrets 时出错: {str(e)}"
        result["error"] = str(e)

    return result


def get_connection_diagnostic_report() -> str:
    """
    获取完整的诊断报告
    """
    import streamlit as st
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("数据库连接诊断报告")
    report_lines.append("=" * 60)
    report_lines.append(f"时间: {os.path.getmtime(__file__)}")
    report_lines.append(f"Python 版本: {sys.version}")
    report_lines.append("")
    
    # 检查 secrets
    secrets_result = diagnose_streamlit_secrets()
    report_lines.append("[Secrets 配置检查]")
    report_lines.append(f"  状态: {'成功' if secrets_result['success'] else '失败'}")
    report_lines.append(f"  消息: {secrets_result['message']}")
    if secrets_result.get('available_sections'):
        report_lines.append(f"  可用配置节: {', '.join(secrets_result['available_sections'])}")
    if secrets_result.get('postgres_config'):
        cfg = secrets_result['postgres_config']
        report_lines.append(f"  PostgreSQL 配置:")
        for key, value in cfg.items():
            report_lines.append(f"    {key}: {value}")
    report_lines.append("")
    
    # 尝试实际连接
    if secrets_result.get('postgres_config'):
        import streamlit as st
        cfg = st.secrets["postgres"]
        
        conn_result = diagnose_postgres_connection(
            host=cfg.get("host", ""),
            port=int(cfg.get("port", 5432)),
            dbname=cfg.get("dbname", ""),
            user=cfg.get("user", ""),
            password=cfg.get("password", ""),
            sslmode=cfg.get("sslmode", "require"),
        )
        
        report_lines.append("[PostgreSQL 连接测试]")
        report_lines.append(f"  状态: {'成功' if conn_result['success'] else '失败'}")
        report_lines.append(f"  消息: {conn_result['message']}")
        if conn_result.get('error_type'):
            report_lines.append(f"  错误类型: {conn_result['error_type']}")
        if conn_result.get('details', {}).get('possible_cause'):
            report_lines.append(f"  可能原因: {conn_result['details']['possible_cause']}")
        if conn_result.get('details', {}).get('server_version'):
            report_lines.append(f"  服务器版本: {conn_result['details']['server_version']}")
        report_lines.append("")
        
    return "\n".join(report_lines)
