CREATE OR REPLACE VIEW v_customer_transactions AS
SELECT 
    c.customer_unique_id,
    o.order_id,
    o.order_purchase_timestamp::DATE AS order_date,
    SUM(i.price) AS total_item_value,
    SUM(i.freight_value) AS total_freight,
    SUM(i.price + i.freight_value) AS total_order_value,
    c.customer_city,
    c.customer_state
FROM raw_orders o
JOIN raw_customers c ON o.customer_id = c.customer_id
JOIN raw_order_items i ON o.order_id = i.order_id
WHERE o.order_status = 'delivered'
GROUP BY 
    c.customer_unique_id, 
    o.order_id, 
    o.order_purchase_timestamp::DATE, 
    c.customer_city, 
    c.customer_state;

select * from v_customer_transactions limit 5;
