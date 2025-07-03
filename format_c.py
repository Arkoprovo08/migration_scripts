import oracledb
import psycopg2
from datetime import datetime

def parse_oracle_date(date_str):
    if date_str:
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except Exception:
            pass
    return None

def migrate_format_c_all():
    # 🔗 Oracle (source)
    src_conn = oracledb.connect(
        user="PWCIMS",
        password="PWCIMS2025",
        dsn=oracledb.makedsn("192.168.0.133", 1521, sid="ORCL")
    )
    src_cursor = src_conn.cursor()

    # 🔗 Postgres (target)
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
            SELECT 
                CREATED_BY, 
                REFID, CONTRACTNAME, BLOCKNAME, DOS_CONTRACT, BLOCKCATEGORY, 
                UPLOAD_OCR, UPLOAD_OCR_NO_REMARK, NAME_OF_DISCOVERY, FORMAT_A_DATE, 
                FORMAT_B_DATE, HYDRO_TYPE, REF_TOPSC_ARTICALNO, CONTRACTOR_PARTIES, 
                AREA_BLOCK, NAME_OF_THE_FIELD, NUMBER_OF_HYDROCARBON, 
                NAME_AUTH_SIG_CONTRA, DESIGNATION, CREATED_ON, AVA_WITH_CONTRACTOR_CHK
            FROM FRAMEWORK01.FORM_COMMERICAL_DIS_FORMAT_C
            WHERE STATUS = '1'
        """)
        header_rows = src_cursor.fetchall()
        print(f"✅ Found {len(header_rows)} headers to migrate.")

        for row in header_rows:
            (
                source_created_by,
                refid, contractor_name, block_name, dos_contract, block_category,
                upload_ocr, upload_ocr_no_remark, name_of_discovery, format_a_date,
                format_b_date, hydro_type, ref_topsc_articalno, contractor_parties,
                area_block, name_of_field, number_of_hydrocarbon,
                name_auth_sig_contra, designation, created_on, ava_with_contractor_chk
            ) = row

            # ✅ Convert Oracle date strings to native date
            format_a_date = parse_oracle_date(format_a_date)
            format_b_date = parse_oracle_date(format_b_date)

            # ✅ Normalize OCR flag
            upload_ocr = 1 if upload_ocr and upload_ocr.strip() == '1' else 0

            # ✅ Tick options logic
            tick_a = 1 if ava_with_contractor_chk and ava_with_contractor_chk.strip() == '1' else 0
            tick_b = 1 if ava_with_contractor_chk and ava_with_contractor_chk.strip() == '2' else 0

            # ✅ Map CREATED_BY
            tgt_cursor.execute("""
                SELECT user_id 
                FROM user_profile.m_user_master 
                WHERE is_migrated = 1 AND migrated_user_id = %s
            """, (source_created_by,))
            mapped_user = tgt_cursor.fetchone()
            created_by = mapped_user[0] if mapped_user else 5

            insert_header_sql = """
                INSERT INTO operator_contracts_agreements.t_format_c_commercial_discovery_header
                (
                    format_c_application_no, contractor_name, block_name, dos_contract,
                    block_category, ocr_available, justification_unavailability_ocr,
                    name_of_discoveries, date_of_discovery, date_of_notification,
                    hydrocarbon_type, ref_topsc_articalno, contractor_parties,
                    area_of_block, name_of_field, num_hydrocarbon_zones,
                    name_of_authorised_signatory, designation, creation_date,
                    tick_option_a, tick_option_b, process_id, created_by, is_active, is_migrated,
                    is_declared, declaration_checkbox, current_status, cluster_checkbox
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING format_c_id
            """

            tgt_cursor.execute(insert_header_sql, (
                refid, contractor_name, block_name, dos_contract, block_category,
                upload_ocr, upload_ocr_no_remark, name_of_discovery, format_a_date,
                format_b_date, hydro_type, ref_topsc_articalno, contractor_parties,
                area_block, name_of_field, number_of_hydrocarbon,
                name_auth_sig_contra, designation, created_on,
                tick_a, tick_b, 14, created_by, 1, 1,
                1, '{}', 'DRAFT', '{}'
            ))

            format_c_id = tgt_cursor.fetchone()[0]
            print(f"➡️  Header migrated: REFID={refid} → format_c_id={format_c_id}")

            # ✅ Fetch exactly one well name, only once
            src_cursor.execute("""
                SELECT MAX(label_input)
                FROM FRAMEWORK01.FORM_COMMERICAL_DIS_FORMAT_C2
                WHERE ACTIVE = '1' AND REFID = :refid AND label_value = 'Well_Name'
            """, [refid])
            well_name = src_cursor.fetchone()[0]

            if well_name:
                tgt_cursor.execute("""
                    INSERT INTO operator_contracts_agreements.t_format_c_well_details
                    (format_c_id, well_name_or_number, created_by, is_active, is_migrated)
                    VALUES (%s, %s, %s, %s, %s)
                """, (format_c_id, well_name, created_by, 1, 1))

                print(f"   ✅ Well detail added for REFID={refid}: Well_Name={well_name}")
            else:
                print(f"   ⚠️  No Well_Name found for REFID={refid}, skipping well details.")

        tgt_conn.commit()
        src_conn.commit()
        print(f"🎉 All FORMAT_C data migrated successfully!")

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        tgt_conn.rollback()
        src_conn.rollback()
    finally:
        src_cursor.close()
        src_conn.close()
        tgt_cursor.close()
        tgt_conn.close()

if __name__ == "__main__":
    migrate_format_c_all()
