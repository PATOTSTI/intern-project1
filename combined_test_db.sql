-- =============================================================
-- COMBINED TEST DATABASE SCRIPT
-- Multi-date, multi-account, multi-transaction-type test data
-- =============================================================
--
-- 5 ACCOUNTS COVERING ALL PROCESSOR ROUTES:
--   001190000001  sendingType=2, format=A  →  process_mt940_new       (field86=Y, writes :86:)
--   001190000002  sendingType=1, format=A  →  process_mt940_swift     (field86=N)
--   001190000003  sendingType=2, format=A  →  process_mt940_new       (NO transactions ever → always blank)
--   001190000004  sendingType=2, format=B  →  process_mt940_converge  (field86=Y, writes :86:)
--   001010039999  sendingType=2, format=A  →  process_mt940_new       (large volume, 26 txns)
--
-- TEST SCHEDULE — enter these dates when prompted by main.py:
--
--  Date      | 001190000001 | 001190000002 | 001190000003 | 001190000004 | 001010039999
--  ----------|--------------|--------------|--------------|--------------|-------------
--  20260210  |  3 txns  ✓  |  3 txns  ✓  |  NO TXN  ✗  |  NO TXN  ✗  |  26 txns ✓
--  20260211  |  NO TXN  ✗  |  NO TXN  ✗  |  NO TXN  ✗  |  2 txns  ✓  |  NO TXN  ✗
--  20260212  |  3 txns  ✓  |  NO TXN  ✗  |  NO TXN  ✗  |  NO TXN  ✗  |  NO TXN  ✗
--  20260213  |  NO TXN  ✗  |  3 txns  ✓  |  NO TXN  ✗  |  3 txns  ✓  |  NO TXN  ✗
--  20260214  |  2 txns  ✓  |  NO TXN  ✗  |  NO TXN  ✗  |  NO TXN  ✗  |  NO TXN  ✗
--
--  Accounts with ✗ on a given date produce a BLANK MT940 file (no :61: lines)
-- =============================================================


-- =============================================================
-- SCHEMA
-- =============================================================

CREATE TABLE IF NOT EXISTS MT940 (
    statementacctno     TEXT PRIMARY KEY,
    counter             INTEGER,
    recipient_swift_bic TEXT,
    date                TEXT,
    code                TEXT,
    sendingType         TEXT,
    filename            TEXT,
    extension_type      TEXT,
    company             TEXT,
    daily               TEXT,
    format              TEXT,
    uploadPath          TEXT,
    field86_flag        TEXT
);

CREATE TABLE IF NOT EXISTS MT940_summary_rep (
    data    TEXT,
    code    TEXT,
    refnum  TEXT,
    date    TEXT
);

CREATE TABLE IF NOT EXISTS acctmstr_copy (
    accountno       TEXT,
    ledger_bal      TEXT,
    available_bal   TEXT
);

CREATE TABLE IF NOT EXISTS acctmstrbefclr_copy (
    accountno       TEXT,
    ledger_bal      TEXT,
    available_bal   TEXT
);

CREATE TABLE IF NOT EXISTS casaSwiftTrancodeMap (
    mnem_code       TEXT,
    swift_trancode  TEXT
);

CREATE TABLE IF NOT EXISTS codetable (
    emailtag            TEXT,
    emailsched          TEXT,
    emailreport         TEXT,
    emailrecipient      TEXT,
    emailrecipientcc    TEXT,
    sentflag            TEXT
);

CREATE TABLE IF NOT EXISTS tlf_copy (
    acctno          TEXT,
    txncode         TEXT,
    mnem_code       TEXT,
    txntype         TEXT,
    txnamt          TEXT,
    refno           TEXT,
    bill_reference  TEXT
);

CREATE TABLE IF NOT EXISTS historyfile1_copy (
    acctno          TEXT,
    branchno        TEXT,
    txnseqno        TEXT,
    txncode         TEXT,
    mnem_code       TEXT,
    txntype         TEXT,
    txn_date        TEXT,
    txn_time        TEXT,
    valuedate       TEXT,
    txnamt          TEXT,
    ledger_bal      TEXT,
    avail_bal       TEXT,
    refno           TEXT,
    passbk_recno    TEXT,
    tellerid        TEXT,
    superid         TEXT,
    delete_flag     TEXT,
    acq_branch      TEXT,
    reconrefno      TEXT
);


-- =============================================================
-- SWIFT TRANSACTION CODE MAP
-- =============================================================
INSERT INTO casaSwiftTrancodeMap (mnem_code, swift_trancode) VALUES
('CASHDEP', 'NMSC'),
('CASHWDL', 'NMSC'),
('CHKDEP',  'NMSC'),
('INTTRF',  'NMSC'),
('INTCRD',  'NMSC'),
('ONLPAY',  'NMSC'),
('CHARGES', 'NMSC'),
('DEFAULT', 'NMSC');


-- =============================================================
-- CODETABLE  (sentflag = 0 → system will process)
-- =============================================================
INSERT INTO codetable (emailtag, emailsched, emailreport, emailrecipient, emailrecipientcc, sentflag)
VALUES
('Y', 'daily', 'MT940',                    'admin@testbank.com',    'reports@testbank.com', '0'),
('Y', 'daily', 'MT940 for 001190000001',   'client1@example.com',   'cc@testbank.com',      '0'),
('Y', 'daily', 'MT940 for 001190000002',   'client2@example.com',   'cc@testbank.com',      '0'),
('Y', 'daily', 'MT940 for 001190000004',   'client4@example.com',   'cc@testbank.com',      '0'),
('Y', 'daily', 'MT940 for 001010039999',   'bigclient@example.com', 'cc@testbank.com',      '0');


-- =============================================================
-- MT940 ACCOUNT CONFIG
-- =============================================================
INSERT INTO MT940
(statementacctno, counter, recipient_swift_bic, date, code, sendingType, filename, extension_type, company, daily, format, uploadPath, field86_flag)
VALUES
-- process_mt940_new  |  has transactions on: 20260210, 20260212, 20260214
('001190000001', 1, 'AUBKPHMMXXX', '20260209', 'AUBKPHMMXXX', '2', NULL, '.txt', 'TESTCO',   '1', 'A', 'C:\UPLOAD\TESTCO\',   'Y'),
-- process_mt940_swift  |  has transactions on: 20260210, 20260213
('001190000002', 1, 'AUBKPHMMXXX', '20260209', 'AUBKPHMMXXX', '1', NULL, '.txt', 'TESTCO',   '1', 'A', 'C:\UPLOAD\TESTCO\',   'N'),
-- process_mt940_new  |  NO transactions on ANY date → always blank file
('001190000003', 1, 'AUBKPHMMXXX', '20260209', 'AUBKPHMMXXX', '2', NULL, '.txt', 'TESTCO',   '1', 'A', 'C:\UPLOAD\TESTCO\',   'N'),
-- process_mt940_converge (format=B)  |  has transactions on: 20260211, 20260213
('001190000004', 1, 'AUBKPHMMXXX', '20260209', 'AUBKPHMMXXX', '2', NULL, '.txt', 'TESTCO',   '1', 'B', 'C:\UPLOAD\TESTCO\',   'Y'),
-- process_mt940_new  |  large volume 26 transactions on 20260210 only
('001010039999', 1, 'XXXXXXXXXXXX', '20260209', 'XXXXXXXXXXXX', '2', NULL, '.txt', 'TESTCOMP', '1', 'A', 'C:\UPLOAD\TESTCOMP\', '0');


-- =============================================================
-- BALANCE SNAPSHOTS  (used for blank file generation)
--   acctmstr_copy       → used by process_mt940_new
--   acctmstrbefclr_copy → used by process_mt940_swift and process_mt940_converge
--   Both tables populated for all accounts to be safe.
--   Values reflect each account's balance BEFORE any of the test transactions.
-- =============================================================
INSERT INTO acctmstr_copy (accountno, ledger_bal, available_bal) VALUES
('001190000001', '50000.00',        '50000.00'),
('001190000002', '100000.00',       '100000.00'),
('001190000003', '25000.00',        '25000.00'),
('001190000004', '200000.00',       '200000.00'),
('001010039999', '129310383.19',    '129310383.19');

INSERT INTO acctmstrbefclr_copy (accountno, ledger_bal, available_bal) VALUES
('001190000001', '50000.00',        '50000.00'),
('001190000002', '100000.00',       '100000.00'),
('001190000003', '25000.00',        '25000.00'),
('001190000004', '200000.00',       '200000.00'),
('001010039999', '129310383.19',    '129310383.19');


-- =============================================================
-- TRANSACTIONS
-- =============================================================

-- -------------------------------------------------------------
-- Account 001190000001  (process_mt940_new, field86=Y)
-- Opening balance: 50,000.00
--
-- DATE 20260210 — 3 transactions (deposit, withdrawal, interest)
-- -------------------------------------------------------------
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000001','001','1','DEP','CASHDEP','C','20260210','090000','20260210','5000.00',  '55000.00', '55000.00', 'A1-REF001','1','T01','S01','N','001',NULL),
('001190000001','001','2','WDL','CASHWDL','D','20260210','113000','20260210','2000.00',  '53000.00', '53000.00', 'A1-REF002','2','T01','S01','N','001',NULL),
('001190000001','001','3','DEP','INTCRD', 'C','20260210','160000','20260210','125.50',   '53125.50', '53125.50', 'A1-REF003','3','T01','S01','N','001',NULL);

-- DATE 20260211 — NO TRANSACTIONS for 001190000001 (blank file)

-- DATE 20260212 — 3 transactions (check deposit, service charge, withdrawal)
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000001','001','4','DEP','CHKDEP', 'C','20260212','094500','20260212','15000.00', '68125.50', '68125.50', 'A1-REF004','1','T01','S01','N','001',NULL),
('001190000001','001','5','WDL','CHARGES','D','20260212','120000','20260212','350.00',   '67775.50', '67775.50', 'A1-REF005','2','T01','S01','N','001',NULL),
('001190000001','001','6','WDL','CASHWDL','D','20260212','153000','20260212','10000.00', '57775.50', '57775.50', 'A1-REF006','3','T01','S01','N','001',NULL);

-- DATE 20260213 — NO TRANSACTIONS for 001190000001 (blank file)

-- DATE 20260214 — 2 transactions (deposit, online payment)
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000001','001','7','DEP','CASHDEP','C','20260214','083000','20260214','20000.00', '77775.50', '77775.50', 'A1-REF007','1','T01','S01','N','001',NULL),
('001190000001','001','8','WDL','ONLPAY', 'D','20260214','141500','20260214','5500.00',  '72275.50', '72275.50', 'A1-REF008','2','T01','S01','N','001',NULL);


-- -------------------------------------------------------------
-- Account 001190000002  (process_mt940_swift, field86=N)
-- Opening balance: 100,000.00
--
-- DATE 20260210 — 3 transactions
-- -------------------------------------------------------------
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000002','001','1','DEP','CASHDEP','C','20260210','090000','20260210','10000.00', '110000.00','110000.00','A2-SW001','1','T02','S01','N','001',NULL),
('001190000002','001','2','WDL','CASHWDL','D','20260210','110000','20260210','3000.00',  '107000.00','107000.00','A2-SW002','2','T02','S01','N','001',NULL),
('001190000002','001','3','DEP','INTTRF', 'C','20260210','150000','20260210','25000.00', '132000.00','132000.00','A2-SW003','3','T02','S01','N','001',NULL);

-- DATE 20260211 — NO TRANSACTIONS for 001190000002 (blank file)
-- DATE 20260212 — NO TRANSACTIONS for 001190000002 (blank file)

-- DATE 20260213 — 3 transactions (large deposit, withdrawal, service charge)
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000002','001','4','DEP','CASHDEP','C','20260213','091500','20260213','50000.00', '182000.00','182000.00','A2-SW004','1','T02','S01','N','001',NULL),
('001190000002','001','5','WDL','CASHWDL','D','20260213','132000','20260213','20000.00', '162000.00','162000.00','A2-SW005','2','T02','S01','N','001',NULL),
('001190000002','001','6','WDL','CHARGES','D','20260213','160000','20260213','500.00',   '161500.00','161500.00','A2-SW006','3','T02','S01','N','001',NULL);

-- DATE 20260214 — NO TRANSACTIONS for 001190000002 (blank file)


-- -------------------------------------------------------------
-- Account 001190000003  (process_mt940_new, field86=N)
-- NO TRANSACTIONS on ANY date → always produces a blank file
-- Balance stays at 25,000.00 on every run
-- -------------------------------------------------------------
-- (intentionally empty)


-- -------------------------------------------------------------
-- Account 001190000004  (process_mt940_converge, format=B, field86=Y)
-- Opening balance: 200,000.00
--
-- DATE 20260210 — NO TRANSACTIONS for 001190000004 (blank file)
-- DATE 20260211 — 2 transactions
-- -------------------------------------------------------------
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000004','002','1','DEP','CASHDEP','C','20260211','090000','20260211','30000.00', '230000.00','230000.00','A4-CV001','1','T03','S01','N','002',NULL),
('001190000004','002','2','WDL','CASHWDL','D','20260211','141500','20260211','8000.00',  '222000.00','222000.00','A4-CV002','2','T03','S01','N','002',NULL);

-- DATE 20260212 — NO TRANSACTIONS for 001190000004 (blank file)

-- DATE 20260213 — 3 transactions (check deposit, online payment, service charge)
INSERT INTO historyfile1_copy
(acctno, branchno, txnseqno, txncode, mnem_code, txntype, txn_date, txn_time, valuedate, txnamt, ledger_bal, avail_bal, refno, passbk_recno, tellerid, superid, delete_flag, acq_branch, reconrefno)
VALUES
('001190000004','002','3','DEP','CHKDEP', 'C','20260213','094500','20260213','45000.00', '267000.00','267000.00','A4-CV003','1','T03','S01','N','002',NULL),
('001190000004','002','4','WDL','ONLPAY', 'D','20260213','121000','20260213','12000.00', '255000.00','255000.00','A4-CV004','2','T03','S01','N','002',NULL),
('001190000004','002','5','WDL','CHARGES','D','20260213','160000','20260213','750.00',   '254250.00','254250.00','A4-CV005','3','T03','S01','N','002',NULL);

-- DATE 20260214 — NO TRANSACTIONS for 001190000004 (blank file)


-- -------------------------------------------------------------
-- Account 001010039999  (process_mt940_new, large volume)
-- Opening balance: 129,310,383.19
--
-- DATE 20260210 ONLY — 26 transactions (all other dates: blank file)
-- -------------------------------------------------------------
INSERT INTO historyfile1_copy
(acctno, txncode, mnem_code, txntype, txn_date, txnamt, ledger_bal, refno, passbk_recno, delete_flag)
VALUES
('001010039999','TC','DEFAULT','C','20260210','100000.00',    '129410383.19','2233720006',       '1', 'N'),
('001010039999','TC','DEFAULT','C','20260210','100000.00',    '129510383.19','2233720007',       '2', 'N'),
('001010039999','TC','DEFAULT','C','20260210','13388.00',     '129523771.19','031871-031871',    '3', 'N'),
('001010039999','TC','DEFAULT','D','20260210','100000.00',    '129423771.19','2233720008',       '4', 'N'),
('001010039999','TC','DEFAULT','D','20260210','100000.00',    '129323771.19','2233720009',       '5', 'N'),
('001010039999','TC','DEFAULT','C','20260210','100000000.00', '229323771.19','2233720010',       '6', 'N'),
('001010039999','TC','DEFAULT','D','20260210','129000400.00', '100323371.19','CP5K2600121665',   '7', 'N'),
('001010039999','TC','DEFAULT','C','20260210','35000.00',     '100358371.19','2223550017',       '8', 'N'),
('001010039999','TC','DEFAULT','C','20260210','1000000.00',   '101358371.19','2232430049',       '9', 'N'),
('001010039999','TC','DEFAULT','C','20260210','10000000.00',  '111358371.19','2232430050',       '10','N'),
('001010039999','TC','DEFAULT','C','20260210','480000.00',    '111838371.19','2172760038',       '11','N'),
('001010039999','TC','DEFAULT','C','20260210','5000000.00',   '116838371.19','2232430051',       '12','N'),
('001010039999','TC','DEFAULT','C','20260210','1000000.00',   '117838371.19','2232430052',       '13','N'),
('001010039999','TC','DEFAULT','C','20260210','500000.00',    '118338371.19','2232430053',       '14','N'),
('001010039999','TC','DEFAULT','C','20260210','2000000.00',   '120338371.19','2232430054',       '15','N'),
('001010039999','TC','DEFAULT','C','20260210','3210.00',      '120341581.19','2193600031',       '16','N'),
('001010039999','TC','DEFAULT','C','20260210','2420938.80',   '122762519.99','2193600038',       '17','N'),
('001010039999','TC','DEFAULT','C','20260210','400.00',       '122762919.99','112558505222',     '18','N'),
('001010039999','TC','DEFAULT','C','20260210','4200000.00',   '126962919.99','5K26TC379M2852',   '19','N'),
('001010039999','TC','DEFAULT','C','20260210','2500000.00',   '129462919.99','2172760096',       '20','N'),
('001010039999','TC','DEFAULT','C','20260210','1000000.00',   '130462919.99','2172760097',       '21','N'),
('001010039999','TC','DEFAULT','C','20260210','500000.00',    '130962919.99','2172760100',       '22','N'),
('001010039999','TC','DEFAULT','C','20260210','1000000.00',   '131962919.99','2172760101',       '23','N'),
('001010039999','TC','DEFAULT','C','20260210','550000.00',    '132512919.99','2172760102',       '24','N'),
('001010039999','TC','DEFAULT','C','20260210','650000.00',    '133162919.99','2172760103',       '25','N'),
('001010039999','TC','DEFAULT','C','20260210','3000000.00',   '136162919.99','2172760104',       '26','N');


-- =============================================================
-- MT940_summary_rep  (cleared and repopulated by the system on each run)
-- =============================================================
-- (intentionally empty)
