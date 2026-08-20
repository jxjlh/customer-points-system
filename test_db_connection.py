"""
数据库连接测试脚本

使用方法：
1. 本地测试：python test_db_connection.py
2. 自动从 .streamlit/secrets.toml 读取配置
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_secrets_from_toml():
    """从 .streamlit/secrets.toml 读取配置（不依赖 streamlit）"""
    toml_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        ".streamlit", "secrets.toml"
    )
    if not os.path.exists(toml_path):
        print(f"❌ 找不到配置文件: {toml_path}")
        return None

    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            try:
                toml = __import__('toml')
            except ImportError:
                print("❌ 需要安装 tomli: pip install tomli")
                return None

    try:
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"❌ 解析配置文件失败: {e}")
        return None


def test_with_psycopg2():
    """直接使用 psycopg2 测试连接"""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ psycopg2 未安装，请运行: pip install psycopg2-binary")
        return False

    secrets = load_secrets_from_toml()
    if not secrets:
        return False

    if "postgres" not in secrets:
        print("❌ secrets.toml 中没有 [postgres] 配置")
        return False

    pg = secrets["postgres"]
    conn_params = {
        'host': pg.get('host', ''),
        'port': int(pg.get('port', 6543)),
        'dbname': pg.get('dbname', 'postgres'),
        'user': pg.get('user', ''),
        'password': pg.get('password', ''),
        'sslmode': pg.get('sslmode', 'require'),
        'connect_timeout': int(pg.get('connect_timeout', 15)),
    }

    print("=" * 50)
    print("🔍 Supabase PostgreSQL 连接测试")
    print("=" * 50)
    print(f"  主机: {conn_params['host']}")
    print(f"  端口: {conn_params['port']}")
    print(f"  数据库: {conn_params['dbname']}")
    print(f"  用户: {conn_params['user']}")
    print(f"  SSL: {conn_params['sslmode']}")
    print("=" * 50)

    try:
        print("\n🔌 正在连接...")
        conn = psycopg2.connect(**conn_params)
        print("✅ 连接成功!")

        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"  PostgreSQL版本: {version[0].split(',')[0]}")

            cur.execute("SELECT current_database(), current_user, now();")
            db, user, now = cur.fetchone()
            print(f"  数据库: {db}")
            print(f"  用户: {user}")
            print(f"  服务器时间: {now}")

            print("\n📊 测试查询...")
            cur.execute("SELECT 1 AS test_value")
            result = cur.fetchone()
            print(f"  查询结果: {result[0]}")
            print("✅ 查询测试通过!")

        conn.close()
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！数据库连接正常")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n❌ 连接失败: {type(e).__name__}: {e}")

        error_str = str(e).lower()
        print("\n💡 错误分析:")
        if "timeout" in error_str:
            print("  🔸 连接超时")
            print("  可能原因：")
            print("  1. Supabase 项目已暂停（免费版 7 天不活动会暂停）")
            print("     → 请登录 https://supabase.com/dashboard 恢复项目")
            print("  2. 网络防火墙阻断了 6543 端口")
            print("     → 检查本地防火墙设置")
        elif "password" in error_str or "authentication" in error_str:
            print("  🔸 认证失败")
            print("  可能原因：")
            print("  1. 密码错误")
            print("     → 登录 Supabase Dashboard → Project Settings → Database 重置密码")
            print("  2. 用户角色不存在")
            print("     → 确认用户名是否正确")
        elif "role" in error_str:
            print("  🔸 角色不存在")
            print("  可能原因：")
            print("  1. 用户角色已被删除")
            print("     → 登录 Supabase Dashboard 检查用户角色")
        elif "connection refused" in error_str:
            print("  🔸 连接被拒绝")
            print("  可能原因：")
            print("  1. 主机地址错误")
            print("     → 确认使用 Supabase Connection Pooler 地址")
            print("  2. 端口错误")
            print("     → Supabase Pooler 使用端口 6543")
        elif "ssl" in error_str:
            print("  🔸 SSL 错误")
            print("  可能原因：")
            print("  1. SSL 模式不兼容")
            print("     → Supabase 要求 sslmode=require")
        elif "name or service not known" in error_str or "nodename nor servname" in error_str:
            print("  🔸 主机名无法解析")
            print("  可能原因：")
            print("  1. 主机地址错误")
            print("     → 确认主机名拼写正确")
            print("  2. DNS 解析失败")
            print("     → 检查 DNS 设置")
        elif "does not exist" in error_str:
            print("  🔸 数据库不存在")
            print("  可能原因：")
            print("  1. 数据库名称错误")
            print("     → Supabase 默认数据库名为 'postgres'")
        else:
            print(f"  未知错误类型: {type(e).__name__}")
            print(f"  详细信息: {str(e)[:300]}")

        print("\n📋 排查清单:")
        print("  1. 登录 Supabase Dashboard (https://supabase.com/dashboard)")
        print("  2. 检查项目是否已暂停（免费版 7 天不活动会暂停）")
        print("  3. 进入 Project Settings → Database → Reset password 重置密码")
        print("  4. 复制新的连接字符串更新到 .streamlit/secrets.toml")
        print("  5. 或在 Streamlit Cloud Secrets 中更新数据库密码")
        return False


if __name__ == "__main__":
    success = test_with_psycopg2()
    sys.exit(0 if success else 1)