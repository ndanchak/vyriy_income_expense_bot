-- 002: Expense refactor — add description and paid_by columns
-- description: free-text expense description (replaces vendor in interactive flow)
-- paid_by: who paid for the expense (Nestor | Ihor | Ira | Other | Account)

ALTER TABLE transactions ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS paid_by VARCHAR;
