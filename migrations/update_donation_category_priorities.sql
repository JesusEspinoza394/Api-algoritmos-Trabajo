BEGIN;

UPDATE donation
SET priority = CASE
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) IN ('alimentos', 'ropa y calzado') THEN 1
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'higiene personal' THEN 2
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) IN ('juguetes', 'utiles escolares') THEN 3
    WHEN lower(translate(
        btrim(object_type),
        'áéíóúüÁÉÍÓÚÜ',
        'aeiouuAEIOUU'
    )) = 'otro' THEN 4
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
