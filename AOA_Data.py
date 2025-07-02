import oracledb
import psycopg2

def migrate_appointment_auditor():
    # Source DB (Oracle)
    src_conn = oracledb.connect(
        user="PWCIMS",
        password="PWCIMS2025",
        dsn=oracledb.makedsn("192.168.0.133", 1521, sid="ORCL")
    )
    src_cursor = src_conn.cursor()

    # Target DB (Postgres)
    tgt_conn = psycopg2.connect(
        host="3.110.185.154",
        port=5432,
        database="ims",
        user="postgres",
        password="P0$tgres@dgh"
    )
    tgt_cursor = tgt_conn.cursor()

    try:
        # Get source rows
        src_cursor.execute("""
            SELECT REFID, CREATED_ON, CREATED_BY, CONTRACTNAME, BLOCKNAME, DOS_CONTRACT,
                   BLOCKCATEGORY, REF_TOPSC_ARTICALNO, NAME_AUDITOR, TOTAL_FEESPAY, DESIGNATION, 
                   NAME_AUTH_SIG_CONTRA, FROM_YEAR, TO_YEAR, OCR_AVAIABLE,
                   OCR_UNAVAIABLE_TXT, BID_ROUND
            FROM FRAMEWORK01.FORM_APPOINTMENT_AUDITOR_OPR
            WHERE status = '1'
        """)

        rows = src_cursor.fetchall()
        print(f"✅ Found {len(rows)} rows to migrate.")

        for row in rows:
            (
                refid, created_on, source_created_by, contractname, blockname, 
                dos_contract, blockcategory, ref_topsc_articalno, name_auditor, total_feespay,
                designation, name_auth_sig_contra, from_year, to_year,
                ocr_avaiable, ocr_unavaiable_txt, bid_round
            ) = row

            # YES/NO ➜ 1/0
            v_is_ocr_available = 1 if ocr_avaiable and ocr_avaiable.strip().upper() == 'YES' else 0

            # 🔑 Resolve actual user_id
            tgt_cursor.execute("""
                SELECT user_id 
                FROM user_profile.m_user_master 
                WHERE is_migrated = 1 AND migrated_user_id = %s
            """, (source_created_by,))
            user_id_result = tgt_cursor.fetchone()
            if not user_id_result:
                print(f"⚠️ No user found for source CREATED_BY = {source_created_by} ➜ skipping REFID {refid}")
                continue

            resolved_user_id = user_id_result[0]

            sql = """
                INSERT INTO operator_contracts_agreements.t_appointment_auditor_details 
                (appointment_auditor_application_number, creation_date, created_by,
                 contractor_name, block_name, dos_contract, block_category, ref_topsc_articalno,
                 name_auditor, total_fees_payable_inr, designation, current_status,
                 name_auth_sig_contra, is_active, audit_period_from, audit_period_to, is_ocr_available, 
                 ocr_unavailable_txt, awarded_under, is_migrated, process_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                refid, created_on, resolved_user_id,  # ✅ use actual user_id here
                contractname, blockname, 
                dos_contract, blockcategory, ref_topsc_articalno, name_auditor, total_feespay,
                designation, 'DRAFT', name_auth_sig_contra, 1, from_year, to_year,
                v_is_ocr_available, ocr_unavaiable_txt, bid_round, 1, 30
            )

            print(f"🔄 Inserting REFID {refid} with user_id {resolved_user_id} ...")
            tgt_cursor.execute(sql, values)
            tgt_conn.commit()
            print(f"✅ Inserted REFID {refid}")

    except Exception as ex:
        print(f"❌ Migration failed: {ex}")
        tgt_conn.rollback()
    finally:
        src_cursor.close()
        src_conn.close()
        tgt_cursor.close()
        tgt_conn.close()
        print("✅ All connections closed.")

if __name__ == "__main__":
    migrate_appointment_auditor()
