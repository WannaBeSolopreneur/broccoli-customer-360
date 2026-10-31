-- Shared cleaning functions. Every model uses these, so a phone or email is
-- cleaned the same way everywhere.

-- Phone to 10 US digits. Accepts +1, dashes, dots, spaces, 10 or 11 digits.
CREATE FUNCTION IF NOT EXISTS c360_digits AS (p) -> replaceRegexpAll(ifNull(p, ''), '[^0-9]', '');
CREATE FUNCTION IF NOT EXISTS c360_phone10 AS (p) -> multiIf(
    length(c360_digits(p)) = 10, c360_digits(p),
    length(c360_digits(p)) = 11 AND startsWith(c360_digits(p), '1'), substring(c360_digits(p), 2),
    NULL);
CREATE FUNCTION IF NOT EXISTS c360_e164 AS (p) -> if(c360_phone10(p) IS NULL, NULL, concat('+1', c360_phone10(p)));

-- Email: trim, lower case, and keep only if it looks valid.
CREATE FUNCTION IF NOT EXISTS c360_email AS (e) -> if(
    match(lower(trimBoth(ifNull(e, ''))), '^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$'),
    lower(trimBoth(ifNull(e, ''))), NULL);

-- Name parts. Handles "Last, First", "First Last", "J. Smith" and any case.
CREATE FUNCTION IF NOT EXISTS c360_clean_token AS (s) -> nullIf(replaceRegexpAll(lower(ifNull(s, '')), '[^a-z]', ''), '');
CREATE FUNCTION IF NOT EXISTS c360_first_raw AS (n) -> if(position(ifNull(n, ''), ',') > 0,
    splitByWhitespace(trimBoth(splitByChar(',', n)[2]))[1],
    splitByWhitespace(trimBoth(ifNull(n, '')))[1]);
CREATE FUNCTION IF NOT EXISTS c360_last_raw AS (n) -> multiIf(
    position(ifNull(n, ''), ',') > 0, trimBoth(splitByChar(',', n)[1]),
    length(splitByWhitespace(trimBoth(ifNull(n, '')))) >= 2, arrayElement(splitByWhitespace(trimBoth(n)), -1),
    NULL);

-- Street line to a match key: house number plus street words, no unit,
-- standard short forms for direction and street type.
CREATE FUNCTION IF NOT EXISTS c360_street_base AS (s) -> replaceRegexpAll(
    replaceRegexpOne(lower(ifNull(s, '')), '[ ,]*(apt|unit|suite|ste|#)\\.?\\s*#?[a-z0-9-]+\\s*$', ''),
    '[^a-z0-9 ]', ' ');
CREATE FUNCTION IF NOT EXISTS c360_street_dirs AS (s) ->
    replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(s,
        '\\bnorth\\b', 'n'), '\\bsouth\\b', 's'), '\\beast\\b', 'e'), '\\bwest\\b', 'w');
CREATE FUNCTION IF NOT EXISTS c360_street_types_a AS (s) ->
    replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(s,
        '\\bstreet\\b', 'st'), '\\b(avenue|av)\\b', 'ave'), '\\bdrive\\b', 'dr'), '\\broad\\b', 'rd');
CREATE FUNCTION IF NOT EXISTS c360_street_types_b AS (s) ->
    replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(replaceRegexpAll(s,
        '\\blane\\b', 'ln'), '\\bcourt\\b', 'ct'), '\\bboulevard\\b', 'blvd'), '\\bplace\\b', 'pl');
CREATE FUNCTION IF NOT EXISTS c360_street_key AS (s) -> nullIf(trimBoth(replaceRegexpAll(
    c360_street_types_b(c360_street_types_a(c360_street_dirs(c360_street_base(s)))), '\\s+', ' ')), '');
CREATE FUNCTION IF NOT EXISTS c360_house_number AS (s) -> nullIf(extract(ifNull(s, ''), '^\\s*(\\d+)'), '');
CREATE FUNCTION IF NOT EXISTS c360_zip5 AS (s) -> nullIf(extract(ifNull(s, ''), '(\\d{5})(?:-\\d{4})?\\s*$'), '');
CREATE FUNCTION IF NOT EXISTS c360_ts AS (s) -> parseDateTimeBestEffortOrNull(nullIf(s, ''), 'UTC');
