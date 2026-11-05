BEGIN;

UPDATE donation
SET priority = CASE
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'alimentos' THEN 1
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'ropa y calzado' THEN 2
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'higiene personal' THEN 3
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) IN ('juguetes', 'utiles escolares', 'otro') THEN 4
    ELSE priority
END
WHERE lower(translate(
    btrim(object_type),
    'áéíóúüÁÉÍÓÚÜ',
    'aeiouuAEIOUU'
)) IN (
    'alimentos',
    'ropa y calzado',
    'higiene personal',
    'juguetes',
    'utiles escolares',
    'otro'
);

COMMIT;
