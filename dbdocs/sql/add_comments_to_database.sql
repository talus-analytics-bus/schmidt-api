COMMENT ON TABLE auth_entity IS 'Authorizing entity information, including associated place, policies, and plans. The authorizing entity is the authority that enacts the policy, which is not necessarily the place that is affected by it.';

COMMENT ON TABLE auth_entity_policy_number IS '1:1 linking table for `auth_entity` to `policy_number`.';

COMMENT ON TABLE "policy" IS 'Policies addressing COVID-19, consisting of elements from documents (corresponding to `file` rows).';

COMMENT ON COLUMN public."policy".id IS 'Policy unique ID';

COMMENT ON COLUMN public."policy".policy_name IS 'Policy unique ID in Airtable, known as a "record ID" there';