-- Tenant scoped access. Customer facing dashboards read only from tenant_api.
-- Each view takes a tenant_id parameter and can never return another tenant's rows.
-- On a ClickHouse server, models/security/row_policies.sql adds the same rule
-- as row policies per tenant user, so even raw SQL is filtered.
CREATE DATABASE IF NOT EXISTS tenant_api;
CREATE OR REPLACE VIEW tenant_api.dim_customer AS SELECT * FROM marts.dim_customer WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_calls AS SELECT * FROM marts.fct_calls WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_leads AS SELECT * FROM marts.fct_leads WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_jobs AS SELECT * FROM marts.fct_jobs WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_invoices AS SELECT * FROM marts.fct_invoices WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_tickets AS SELECT * FROM marts.fct_tickets WHERE tenant_id = {tenant_id:String};
CREATE OR REPLACE VIEW tenant_api.fct_memberships AS SELECT * FROM marts.fct_memberships WHERE tenant_id = {tenant_id:String};
