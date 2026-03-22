# Graph node and edge type constants

NODE_TYPES = [
    "SalesOrder",
    "SalesOrderItem",
    "Customer",
    "Product",
    "Plant",
    "Delivery",
    "DeliveryItem",
    "BillingDocument",
    "JournalEntry",
    "Payment",
]

EDGE_TYPES = [
    "HAS_ITEM",         # SalesOrder→SalesOrderItem, Delivery→DeliveryItem, BillingDocument→BillingItem
    "PLACED_BY",        # SalesOrder→Customer
    "REF_MATERIAL",     # SalesOrderItem→Product, DeliveryItem→Product, BillingDocumentItem→Product
    "FULFILLED_BY",     # SalesOrderItem→DeliveryItem
    "BILLED_VIA",       # DeliveryItem→BillingDocument
    "HAS_JOURNAL",      # BillingDocument→JournalEntry
    "SHIPS_FROM",       # Delivery→Plant
    "PAID_BY",          # JournalEntry→Payment
    "SOLD_TO",          # BillingDocument→Customer
]

# Human-readable labels for schema injection into LLM prompt
SCHEMA_DESCRIPTION = """
## Graph Node Types
- SalesOrder: id=salesOrder, fields: salesOrderType, soldToParty, totalNetAmount, overallDeliveryStatus, transactionCurrency, creationDate
- SalesOrderItem: id=salesOrder+salesOrderItem, fields: material, requestedQuantity, netAmount, productionPlant
- Customer: id=businessPartner, fields: businessPartnerFullName, businessPartnerCategory, creationDate
- Product: id=product, fields: productType, productOldId, grossWeight, weightUnit, baseUnit
- Plant: id=plant, fields: plantName, salesOrganization
- Delivery: id=deliveryDocument, fields: shippingPoint, overallGoodsMovementStatus, overallPickingStatus, creationDate
- DeliveryItem: id=deliveryDocument+deliveryDocumentItem, fields: plant, actualDeliveryQuantity, deliveryQuantityUnit
- BillingDocument: id=billingDocument, fields: billingDocumentType, totalNetAmount, transactionCurrency, billingDocumentDate, accountingDocument, soldToParty, billingDocumentIsCancelled
- JournalEntry: id=accountingDocument+accountingDocumentItem, fields: glAccount, referenceDocument, amountInTransactionCurrency, postingDate, accountingDocumentType
- Payment: id=accountingDocument+accountingDocumentItem (from payments table), fields: clearingAccountingDocument, clearingDate, amountInTransactionCurrency, customer

## Edge Types
- SalesOrder -[HAS_ITEM]→ SalesOrderItem
- SalesOrder -[PLACED_BY]→ Customer
- SalesOrderItem -[REF_MATERIAL]→ Product
- SalesOrderItem -[FULFILLED_BY]→ DeliveryItem  (via referenceSdDocument + referenceSdDocumentItem)
- Delivery -[HAS_ITEM]→ DeliveryItem
- Delivery -[SHIPS_FROM]→ Plant
- DeliveryItem -[BILLED_VIA]→ BillingDocument  (via referenceSdDocument on billing_document_items)
- BillingDocument -[HAS_JOURNAL]→ JournalEntry  (via accountingDocument)
- BillingDocument -[SOLD_TO]→ Customer
- JournalEntry -[PAID_BY]→ Payment  (via accountingDocument match)

## DuckDB Tables (SQL-queryable)
- sales_order_headers: salesOrder (PK), salesOrderType, soldToParty, totalNetAmount, overallDeliveryStatus, transactionCurrency, creationDate
- sales_order_items: salesOrder, salesOrderItem, material, requestedQuantity, netAmount, productionPlant, storageLocation, materialGroup
- sales_order_schedule_lines: salesOrder, salesOrderItem, scheduleLine, confirmedDeliveryDate, confdOrderQtyByMatlAvailCheck
- outbound_delivery_headers: deliveryDocument (PK), shippingPoint, overallGoodsMovementStatus, overallPickingStatus, creationDate
- outbound_delivery_items: deliveryDocument, deliveryDocumentItem, plant, referenceSdDocument, referenceSdDocumentItem, actualDeliveryQuantity
- billing_document_headers: billingDocument (PK), billingDocumentType, totalNetAmount, transactionCurrency, billingDocumentDate, accountingDocument, soldToParty, billingDocumentIsCancelled
- billing_document_items: billingDocument, billingDocumentItem, material, billingQuantity, netAmount, referenceSdDocument (=deliveryDocument), referenceSdDocumentItem
- journal_entry_items: companyCode, fiscalYear, accountingDocument, accountingDocumentItem, glAccount, referenceDocument (=billingDocument), amountInTransactionCurrency, postingDate, customer, clearingAccountingDocument
- payments: accountingDocument, accountingDocumentItem, clearingDate, clearingAccountingDocument, amountInTransactionCurrency, customer, postingDate
- business_partners: businessPartner (PK), businessPartnerFullName, businessPartnerCategory, businessPartnerIsBlocked
- plants: plant (PK), plantName, salesOrganization
- products: product (PK), productType, productOldId, grossWeight, weightUnit, baseUnit
- product_descriptions: product, language, productDescription
"""
