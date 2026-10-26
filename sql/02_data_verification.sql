SELECT 'raw_customers' AS table_name, count(*) AS total_rows FROM raw_customers
UNION ALL
SELECT 'raw_orders', count(*) FROM raw_orders
UNION ALL
SELECT 'raw_order_items', count(*) FROM raw_order_items;
