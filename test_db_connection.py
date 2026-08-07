"""
数据库连接测试脚本

使用方法：
1. 本地测试：python test_db_connection.py
2. Streamlit Cloud：将此文件部署后访问 /test_db 路由
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_with_psycopg2():
    """直接使用 psycopg2 测试连接"""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("❌ psycopg2 未安装，请运行: pip install psycopg2-binary")
        return False

    # Supabase 连接配置
    conn_params = {
        'host': 'aws-0-ap-northeast-1.pooler.supabase.com',
        'port': 5432,
        'dbname': 'postgres',
        'user': 'postgres.qquxbarjqnkryfutklro',
        'password': 'LH040828@',
        'sslmode': 'require'
    }

    print("=" * 50)
    print("🔍 Supabase PostgreSQL 连接测试")
    print("=" * 50)
    print(f"  主机: {conn_params['host']}")
    print(f"  端口: {conn_params['port']}")
    print(f"  数据库: {conn_params['dbname']}")
    print(f"  用户: {conn_params['user']}")
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

            # 测试创建表
            print("\n📊 测试创建表...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    test_name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("INSERT INTO connection_test (test_name) VALUES (%s)", ("数据库连接测试",))
            conn.commit()
            print("✅ 表创建成功!")

            cur.execute("SELECT COUNT(*) FROM connection_test")
            count = cur.fetchone()[0]
            print(f"  测试记录数: {count}")

            # 清理
            cur.execute("DROP TABLE connection_test")
            conn.commit()
            print("  🧹 测试表已清理")

        conn.close()
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！数据库连接正常")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        print("\n💡 排查建议:")
        print("  1. 检查主机地址是否正确")
        print("  2. 检查用户名和密码")
        print("  3. 确认数据库已创建")
        print("  4. 检查网络连接")
        return False


def test_with_streamlit():
    """Streamlit 环境测试"""
    try:
        import streamlit as st
        from modules.db_manager import get_db_manager

        st.set_page_config(page_title="数据库连接测试", page_icon="🔍")
        st.title("🔍 数据库连接测试")

        db_type = "未配置"
        try:
            if "postgres" in st.secrets:
                db_type = "PostgreSQL"
            elif "mysql" in st.secrets:
                db_type = "MySQL"
        except Exception:
            pass

        st.info(f"检测到数据库类型: **{db_type}**")

        try:
            st.write("正在连接数据库...")
            db = get_db_manager()
            ping_ok = db.ping()

            if ping_ok:
                st.success("✅ 数据库连接成功!")

                st.write("正在初始化表结构...")
                db.init_schema()
                st.success("✅ 表结构初始化成功!")

                # 测试报价单功能
                st.write("正在测试报价单功能...")
                quote_num = db.get_next_quote_number()
                st.write(f"  生成报价单号: {quote_num}")

                # 测试价格库
                st.write("正在测试价格库功能...")
                loaded = db.is_price_loaded()
                st.write(f"  价格库状态: {'已加载' if loaded else '未加载'}")

                st.success("✅ 所有功能测试通过!")
            else:
                st.error("❌ 数据库连接失败")

        except Exception as e:
            st.error(f"❌ 测试出错: {e}")
            st.code(str(e))

    except ImportError:
        print("此脚本需要在 Streamlit 环境中运行")


if __name__ == "__main__":
    # 命令行模式
    success = test_with_psycopg2()
    sys.exit(0 if success else 1)
