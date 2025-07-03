import oracledb
import psycopg2

def migrate_profit_petrol():
    # ✅ Oracle 1.0 connection
    src_conn = oracledb.connect(
        user="PWCIMS",
        password="PWCIMS2025",
        dsn=oracledb.makedsn("192.168.0.133", 1521, sid="ORCL")
    )
    src_cursor = src_conn.cursor()

    # ✅ Postgres 2.0 connection
    tgt_conn = psycopg2.connect(
        host="3.110.185.154",
        port=5432,
        database="ims",
        user="postgres",
        password="P0$tgres@dgh"
    )
    tgt_cursor = tgt_conn.cursor()

    try:
        # ✅ Fetch all rows
        src_cursor.execute("""
            SELECT 
                REFID, BLOCKCATEGORY, BLOCKNAME, CONTRACTNAME, DATE_EFFECTIVE, PROFIT_PETROLEUM, PETROLEUM_DATE,
                PETROLEUM_AMOUNT, PETROLEUM_UTR, PROFIT_PETROLEUM_DEPOSITED, FROM_DATE_INTEREST, AMOUNT_INTEREST,
                UTR, DOES_MC, COMPLIANCE_PSC, NAME_AUTH_SIG_CONTRA, DESIGNATION, CREATED_BY, CREATED_ON, IS_ACTIVE,
                TO_DATE_INTEREST, DATE_INTEREST, DOS_CONTRACT, BID_ROUND
            FROM FRAMEWORK01.FORM_PROFIT_PETROLEUM
            WHERE STATUS = '1'
        """)
        rows = src_cursor.fetchall()
        print(f"✅ Found {len(rows)} records to migrate.")

        for row in rows:
            (
                refid, block_category, block_name, contractor_name, date_effective, profit_petroleum, petroleum_date,
                petroleum_amount, petroleum_utr, profit_petroleum_deposited, from_date_interest, amount_interest,
                utr, does_mc, compliance_psc, name_auth_sig_contra, designation, source_created_by, created_on,
                is_active, to_date_interest, date_interest, dos_contract, bid_round
            ) = row

            # ✅ Set to NULL if 0 or None
            psc_date_amt_provisional_profit = None if not profit_petroleum or profit_petroleum == '0'else profit_petroleum

            # ✅ Map DOES_MC, COMPLIANCE_PSC
            v_does_mc = 1 if does_mc and does_mc.strip().upper() == 'YES' else 0
            v_compliance_psc = 1 if compliance_psc and compliance_psc.strip().upper() == 'YES' else 0

            # ✅ Map CREATED_BY to 2.0 user ID
            tgt_cursor.execute("""
                SELECT user_id 
                FROM user_profile.m_user_master 
                WHERE is_migrated = 1 AND migrated_user_id = %s
            """, (source_created_by,))
            mapped_user = tgt_cursor.fetchone()
            final_created_by = mapped_user[0] if mapped_user else 5

            # ✅ Insert to Postgres
            tgt_cursor.execute("""
                INSERT INTO financial_mgmt.t_cost_and_profit_petroleum_calculations
                (
                    quarterly_report_cost_and_profit_petroleum_calculations_applica,
                    block_category, block_name, contractor_name, effective_date,
                    psc_date_amt_provisional_profit, psc_1_date, psc_1_amount_usd, psc_1_utr_details,
                    psc_2_from_date, psc_2_amount_usd, psc_2_utr_details,
                    psc_mc_approved_audited_acc, psc_compliance_of_psc, name_authorised_signatory, designation,
                    created_by, creation_date, is_active, psc_2_to_date, psc_2_date,
                    dos_contract, awarded_under, is_migrated, is_declared, process_id, current_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1, 34, 'DRAFT')
            """, (
                refid, block_category, block_name, contractor_name, date_effective,
                psc_date_amt_provisional_profit, petroleum_date, petroleum_amount, petroleum_utr,
                from_date_interest, amount_interest, utr,
                v_does_mc, v_compliance_psc, name_auth_sig_contra, designation,
                final_created_by, created_on, is_active, to_date_interest, date_interest,
                dos_contract, bid_round
            ))

            print(f"➡️ Migrated REFID={refid} with created_by={final_created_by} and provisional_profit={psc_date_amt_provisional_profit}")

        tgt_conn.commit()
        print("🎉 Migration completed successfully.")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        tgt_conn.rollback()
    finally:
        src_cursor.close()
        src_conn.close()
        tgt_cursor.close()
        tgt_conn.close()

if __name__ == "__main__":
    migrate_profit_petrol()
