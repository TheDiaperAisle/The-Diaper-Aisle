# Dip Aisle — shipping costs by store (checked 2026-10-30)

Applied on the tracker as the "Delivered" column for every package (samples, bags, cases): (package price + shipping for an order of just that package) ÷ units, before tax. The $/L column ("Delivered $/L") also uses the delivered unit price. Rules are a `SHIP` constant in the page's script; update it there if a store changes its policy.

| Store | Rule | How checked |
| --- | --- | --- |
| Healthwick | Flat fee per order, never free: ON $12; QC/MB/AB/SK $15; BC/NB/NS/PE/NL $18. Free pick-up in Oakville. | Live checkout quote (Shopify cart shipping estimate) for ON, QC, AB, BC, NS; a 5-case $380 order still paid $12 in ON. |
| AgeComfort | $12.99 under $100, free at $100+ (before tax). Remote air-stage areas $49.99, no free shipping. | Shipping policy page (checkout not reachable from the cloud: www.agecomfort.com is not on the allowlist). |
| MyDips (now mydips.store) | ON/QC: $14.99 under $129, $12.99 at $129+. AB/MB/SK/PE/NS/BC: $24.99. NL quoted by Canada Post; NB not listed. Never free. | Shipping policy page. |
| ABUniverse | Free economy shipping on every order, even one 10-pack (paid faster options from ~$14). Currently cannot ship samples or scented options to Canada. | Live checkout quote, ON and BC, 1–8 packs. Sells packs, not cases. |
| Rearz (ca.rearz.ca, BigCommerce) | Free economy shipping at $100+ to all provinces except NB, NS, PE, NL. Otherwise carrier quote minus 25% of order value. | Shipping & Returns and Shipping Discounts pages. |
| Amazon.ca | Free shipping on $35+ of items sold or fulfilled by Amazon (Prime always free); below $35 or some third-party sellers: set at checkout ("quote"). | Amazon.ca help page "Order with Free Shipping by Amazon", 2026-10-31. |

Impact on case unit prices (Oct catalogue, shipping to Ontario): Healthwick adds a median $0.21/unit (+8%); MyDips $0.33/unit (+8%); AgeComfort and Rearz cases are almost all over their free-shipping minimums, so $0. To BC: Healthwick +$0.32 (+12%), MyDips +$0.63 (+15%).

To verify the policy-only stores at checkout, add `www.agecomfort.com` and `mydips.store` to the network allowlist; the cart estimate script is the same one used for Healthwick/ABUniverse (`/cart/add.js` then `/cart/shipping_rates.json`).


## Well.ca (added 2026-11-02)
Free shipping on orders $35+ (before tax) to most Canadian addresses. Below $35, and to remote/air-stage areas, the fee is shown at checkout (not published), so the tracker shows the price before shipping with a "+ shipping" tag. Source: https://well.ca/shipping
