import oracledb
import psycopg2
import re

def split_name(name):
    """
    Basic name splitter: 'John A Doe' => first: John, middle: A, last: Doe
    """
    if not name:
        return '', '', ''
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0], '', ''
    elif len(parts) == 2:
        return parts[0], '', parts[1]
    else:
        return parts[0], ' '.join(parts[1:-1]), parts[-1]

def migrate_user_master():
    # === Source: Oracle ===
    src_conn = oracledb.connect(
        user="PWCIMS",
        password="PWCIMS2025",
        dsn=oracledb.makedsn("192.168.0.133", 1521, sid="ORCL")
    )
    src_cursor = src_conn.cursor()

    # === Target: PostgreSQL ===
    tgt_conn = psycopg2.connect(
        host="3.110.185.154",
        port=5432,
        database="ims",
        user="postgres",
        password="P0$tgres@dgh"
    )
    tgt_cursor = tgt_conn.cursor()

    try:
        src_cursor.execute("""
            SELECT Userid, NAME, EMAIL, PHONE, ROLE, DESIGNATION,
                   IS_LOCKED, USER_STATUS
            FROM XUSER.EXT_USER_MASTER
            WHERE APPID = 301
        """)

        rows = src_cursor.fetchall()
        print(f"✅ Found {len(rows)} rows to migrate.")

        for row in rows:
            try:
                (userid, name, email, phone, role, designation,
                 is_locked, user_status) = row

                first_name, middle_name, last_name = split_name(name)
                full_name = name

                is_active = 1 if user_status and user_status.strip().upper() == 'ACTIVE' else 0

                sql = """
                    INSERT INTO USER_PROFILE.m_user_master
                    (migrated_user_id, first_name, middle_name, last_name, full_name, 
                     user_name, mobile_no, email_id, department_name, designation, 
                     user_mode, is_account_locked, is_active, 
                     is_migrated, is_password_changed)
                    VALUES (%s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s)
                """

                values = (
                    userid, first_name, middle_name, last_name, full_name,
                    email, phone, email, role, designation, 'e',
                    is_locked, is_active, 1, 0
                )

                tgt_cursor.execute(sql, values)
                tgt_conn.commit()  # Commit after each successful insert
                print(f"✅ Inserted UserID {userid}")

            except Exception as insert_ex:
                tgt_conn.rollback()  # Rollback partial insert
                print(f"❌ Error inserting UserID {userid}: {insert_ex}")
                continue

        print("✅ All rows processed.")

    except Exception as main_ex:
        print(f"❌ Migration failed: {main_ex}")

    finally:
        src_cursor.close()
        src_conn.close()
        tgt_cursor.close()
        tgt_conn.close()
        print("✅ Connections closed.")

if __name__ == "__main__":
    migrate_user_master()
