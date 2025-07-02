import oracledb
import psycopg2

def migrate_bg_data():
    # 1️⃣ Connect to Oracle (source)
    src_conn = oracledb.connect(
        user="PWCIMS",
        password="PWCIMS2025",
        dsn=oracledb.makedsn("192.168.0.133", 1521, sid="ORCL")
    )
    src_cursor = src_conn.cursor()

    # 2️⃣ Connect to Postgres (target)
    tgt_conn = psycopg2.connect(
        host="3.110.185.154",
        port=5432,
        database="ims",
        user="postgres",
        password="P0$tgres@dgh"
    )
    tgt_cursor = tgt_conn.cursor()

    try:
        # 3️⃣ Get all rows to migrate
        src_cursor.execute("""
            SELECT 
                REFID, DOS_CONTRACT, BLOCKNAME, BLOCKCATEGORY,
                REF_TOPSC_ARTICALNO, NAME_AUTH_SIG_CONTRA, DESIGNATION, CREATED_BY,
                CREATED_ON, REMARKS, CONTRACTNAME, BG_NO, DATE_OF_BG, DATE_OF_EXP_BG,
                CLIAM_OF_EXP_DATE_OF_BG, APPLICABLE_PERC_BG,
                AMT_OF_BG, USD_INTO_INR, EXCHANGE_RATE_TAKEN, EXCHANGE_RATE_DATE,
                NAME_OF_BANK, SCHEDULED_UNDER_RBI, ADDRESS_OF_BANK, SIG_DIGITAL_SIG,
                IS_BG_FORMAT_PSC, BG_REVISED_EXTENDED_CHK,
                USD_INR, BG_SUBMITTED_BY, NEW_PREV_BG_LINKED, PREV_BG_LINKED_DET,
                CONSORTIUM
            FROM FRAMEWORK01.FORM_SUB_BG_LEGAL_RENEWAL
            WHERE STATUS = '1'
        """)

        rows = src_cursor.fetchall()
        print(f"✅ Total rows fetched: {len(rows)}")

        # 4️⃣ Organize rows by REFID
        data_by_refid = {}
        for row in rows:
            refid = row[0]
            if refid not in data_by_refid:
                data_by_refid[refid] = []
            data_by_refid[refid].append(row)

        print(f"✅ Unique REFIDs: {len(data_by_refid)}")

        # 5️⃣ Migrate each REFID group
        for refid, rows in data_by_refid.items():
            first_row = rows[0]
            (
                _refid, dos_contract, blockname, blockcategory,
                ref_topsc_articalno, name_auth_sig_contra, designation, source_created_by,
                created_on, remarks, contractor_name, *_  # Ignore details columns here
            ) = first_row

            # ✅ Resolve actual user_id — fallback to NULL if not found
            tgt_cursor.execute("""
                SELECT user_id 
                FROM user_profile.m_user_master 
                WHERE is_migrated = 1 AND migrated_user_id = %s
            """, (source_created_by,))
            user_id_result = tgt_cursor.fetchone()
            resolved_user_id = user_id_result[0] if user_id_result else None

            if resolved_user_id is None:
                print(f"⚠️ No user found for CREATED_BY = {source_created_by} ➜ inserting NULL for created_by")

            # Insert into header table
            header_sql = """
                INSERT INTO financial_mgmt.t_bank_gurantee_header
                (
                    bank_gurantee_application_number, dos_contract, block_name, 
                    block_category, ref_topsc_artical_no, name_auth_sig_contra, designation, 
                    created_by, creation_date, remarks, contractor_name, process_id, is_migrated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING bank_gurantee_header_id
            """
            header_values = (
                refid, dos_contract, blockname,
                blockcategory, ref_topsc_articalno, name_auth_sig_contra, designation,
                resolved_user_id, created_on, remarks, contractor_name, 18,1
            )

            tgt_cursor.execute(header_sql, header_values)
            header_id = tgt_cursor.fetchone()[0]
            print(f"✅ Inserted header REFID {refid} ➜ bank_gurantee_header_id {header_id}")

            # Insert each detail row
            for row in rows:
                (
                    _refid, _dos_contract, _blockname, _blockcategory,
                    _ref_topsc_articalno, _name_auth_sig_contra, _designation, _created_by,
                    _created_on, _remarks, _contractor_name, bg_no, date_of_bg, date_of_exp_bg,
                    cliam_of_exp_date_of_bg, applicable_perc_bg,
                    amt_of_bg, usd_into_inr, exchange_rate_taken, exchange_rate_date,
                    name_of_bank, scheduled_under_rbi, address_of_bank, sig_digital_sig,
                    is_bg_format_psc, bg_revised_extended_chk,
                    usd_inr, bg_submitted_by, new_prev_bg_linked, prev_bg_linked_det,
                    consortium
                ) = row

                detail_sql = """
                    INSERT INTO financial_mgmt.t_bank_gurantee_details
                    (
                        contractor_name, bg_no, date_of_bg, date_of_exp_bg, cliam_of_exp_date_of_bg,
                        applicable_perc_bg, amt_of_bg, usd_into_inr,
                        exchange_rate_taken, exchange_rate_date, name_of_bank, scheduled_under_rbi,
                        address_of_bank, sig_digital_sig, current_status, is_bg_format_psc,
                        bg_revised_extended_chk, usd_inr, bg_submitted_by, new_prev_bg_linked,
                        prev_bg_linked_det, consortium, bank_gurantee_header_id, is_migrated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)

                """

                detail_values = (
                    _contractor_name, bg_no, date_of_bg, date_of_exp_bg, cliam_of_exp_date_of_bg,
                    applicable_perc_bg, amt_of_bg, usd_into_inr,
                    exchange_rate_taken, exchange_rate_date, name_of_bank, scheduled_under_rbi,
                    address_of_bank, sig_digital_sig, 'DRAFT',  is_bg_format_psc,
                    bg_revised_extended_chk, usd_inr, bg_submitted_by, new_prev_bg_linked,
                    prev_bg_linked_det, consortium, header_id, 1
                )

                tgt_cursor.execute(detail_sql, detail_values)

            # Commit after each REFID group
            tgt_conn.commit()
            print(f"✅ Inserted {len(rows)} details for REFID {refid}")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        tgt_conn.rollback()
    finally:
        src_cursor.close()
        src_conn.close()
        tgt_cursor.close()
        tgt_conn.close()
        print("✅ All connections closed.")

if __name__ == "__main__":
    migrate_bg_data()
