import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_no TEXT UNIQUE,
                customer TEXT,
                exchange_date TEXT,
                points_exchanged INTEGER,
                amount_exchanged REAL,
                exchange_method TEXT,
                exchange_product TEXT,
                operator TEXT,
                remark TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customer_points_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer TEXT,
                period TEXT,
                total_points_earned INTEGER,
                total_points_exchanged INTEGER,
                remaining_points INTEGER,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS raw_data_backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                order_no TEXT,
                customer TEXT,
                amount REAL,
                amount_cny REAL,
                product TEXT,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_type TEXT,
                message TEXT,
                created_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_exchange_record(self, exchange_no, customer, exchange_date, points_exchanged, 
                            amount_exchanged, exchange_method, exchange_product, 
                            operator, remark=""):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO exchange_records 
                (exchange_no, customer, exchange_date, points_exchanged, amount_exchanged,
                 exchange_method, exchange_product, operator, remark, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (exchange_no, customer, exchange_date, points_exchanged, amount_exchanged,
                  exchange_method, exchange_product, operator, remark, now, now))
            
            conn.commit()
            self.add_log("INFO", f"添加兑换记录: {exchange_no} - {customer}")
            return True
        except Exception as e:
            conn.rollback()
            self.add_log("ERROR", f"添加兑换记录失败: {str(e)}")
            return False
        finally:
            conn.close()
    
    def get_exchange_records(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM exchange_records ORDER BY exchange_date DESC')
        records = cursor.fetchall()
        
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, record)) for record in records]
        
        conn.close()
        return result
    
    def get_exchange_record_by_no(self, exchange_no):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM exchange_records WHERE exchange_no = ?', (exchange_no,))
        record = cursor.fetchone()
        
        if record:
            columns = [desc[0] for desc in cursor.description]
            result = dict(zip(columns, record))
        else:
            result = None
        
        conn.close()
        return result
    
    def delete_exchange_record(self, exchange_no):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM exchange_records WHERE exchange_no = ?', (exchange_no,))
            conn.commit()
            self.add_log("INFO", f"删除兑换记录: {exchange_no}")
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            self.add_log("ERROR", f"删除兑换记录失败: {str(e)}")
            return False
        finally:
            conn.close()
    
    def save_customer_points_history(self, customer, period, total_points_earned, 
                                     total_points_exchanged, remaining_points):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO customer_points_history
                (customer, period, total_points_earned, total_points_exchanged, 
                 remaining_points, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (customer, period, total_points_earned, total_points_exchanged, 
                  remaining_points, now))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            self.add_log("ERROR", f"保存积分历史失败: {str(e)}")
            return False
        finally:
            conn.close()
    
    def get_customer_points_history(self, customer=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if customer:
            cursor.execute('''
                SELECT * FROM customer_points_history 
                WHERE customer = ? ORDER BY period DESC
            ''', (customer,))
        else:
            cursor.execute('''
                SELECT * FROM customer_points_history ORDER BY period DESC
            ''')
        
        records = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, record)) for record in records]
        
        conn.close()
        return result
    
    def backup_raw_data(self, df_raw):
        if df_raw is None or df_raw.empty:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        count = 0
        
        try:
            for _, row in df_raw.iterrows():
                cursor.execute('''
                    INSERT INTO raw_data_backup 
                    (date, order_no, customer, amount, amount_cny, product, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(row.get("日期", "")),
                    str(row.get("单据编号", "")),
                    str(row.get("客户", "")),
                    float(row.get("金额", 0)),
                    float(row.get("金额（本位币）", 0)),
                    str(row.get("货号", "")),
                    now
                ))
                count += 1
            
            conn.commit()
            self.add_log("INFO", f"备份原始数据: {count} 条记录")
            return count
        except Exception as e:
            conn.rollback()
            self.add_log("ERROR", f"备份原始数据失败: {str(e)}")
            return 0
        finally:
            conn.close()
    
    def add_log(self, log_type, message):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            cursor.execute('''
                INSERT INTO system_logs (log_type, message, created_at)
                VALUES (?, ?, ?)
            ''', (log_type, message, now))
            conn.commit()
        except:
            pass
        finally:
            conn.close()
    
    def get_logs(self, limit=100):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM system_logs ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        
        records = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        result = [dict(zip(columns, record)) for record in records]
        
        conn.close()
        return result
    
    def sync_exchange_from_excel(self, df_exchange):
        if df_exchange is None or df_exchange.empty:
            return 0
        
        count = 0
        for _, row in df_exchange.iterrows():
            exchange_no = str(row.get("兑换编号", ""))
            if exchange_no:
                success = self.add_exchange_record(
                    exchange_no=exchange_no,
                    customer=str(row.get("客户", "")),
                    exchange_date=str(row.get("兑换日期", "")),
                    points_exchanged=int(row.get("兑换积分数量", 0)),
                    amount_exchanged=float(row.get("兑换金额", 0)),
                    exchange_method=str(row.get("兑换方式", "")),
                    exchange_product=str(row.get("兑换产品", "")),
                    operator=str(row.get("操作人员", "")),
                    remark=str(row.get("备注", ""))
                )
                if success:
                    count += 1
        
        return count
