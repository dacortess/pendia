-- Categorías del sistema (group_id NULL) — precargadas una sola vez,
-- disponibles para todos los grupos. Un grupo puede además crear sus
-- propias categorías personalizadas (group_id = su id) sin colisionar
-- con estos nombres (unicidad separada, ver schema.sql).

INSERT INTO categories (group_id, name, icon) VALUES
    (NULL, 'Servicios del hogar', 'home'),          -- luz, agua, gas, internet, aseo
    (NULL, 'Suscripciones',       'tv'),             -- streaming, revistas, juegos, software
    (NULL, 'Salud',                'heart'),         -- medicina prepagada, planes preferenciales, EPS complementaria
    (NULL, 'Educación',           'book'),
    (NULL, 'Seguros',             'shield'),         -- vida, hogar, vehículo
    (NULL, 'Transporte',          'car'),
    (NULL, 'Créditos y deudas',   'credit-card'),
    (NULL, 'Alimentación',        'shopping-cart'),
    (NULL, 'Entretenimiento',     'film'),
    (NULL, 'Otros',               'more-horizontal')
ON CONFLICT DO NOTHING;
