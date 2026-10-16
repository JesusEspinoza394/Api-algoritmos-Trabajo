BEGIN;

ALTER TABLE donation
    ADD COLUMN IF NOT EXISTS priority INTEGER;

UPDATE donation
SET priority = CASE
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) IN ('juguetes', 'utiles escolares', 'otro') THEN 1
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'higiene personal' THEN 2
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'ropa y calzado' THEN 3
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'alimentos' THEN 4
    ELSE 1
END;

ALTER TABLE donation
    ALTER COLUMN priority SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_donation_priority
    ON donation (priority);

COMMIT;
