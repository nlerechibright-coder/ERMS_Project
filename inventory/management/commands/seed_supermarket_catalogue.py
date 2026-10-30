from decimal import Decimal

from django.core.management.base import BaseCommand

from inventory.models import Product, ProductCategory

CATEGORIES = [
    'Noodles and pasta',
    'Rice and grains',
    'Cooking oil and food ingredients',
    'Beverages and bottled water',
    'Biscuits, snacks and confectionery',
    'Milk and packaged food',
    'Household cleaning products',
    'Toiletries and personal care',
    'Canned and packaged foods',
]

# sku, name, category, stock_unit, purchase_unit, units_per_purchase_unit, brand
PRODUCTS = [
    ('ND-IND-CHK', 'Indomie Chicken Flavour Noodles', 'Noodles and pasta', 'pack', 'carton', 40, 'Indomie'),
    ('ND-IND-CUR', 'Indomie Curry Flavour Noodles', 'Noodles and pasta', 'pack', 'carton', 40, 'Indomie'),
    ('ND-GOL-SPA', 'Golden Penny Spaghetti', 'Noodles and pasta', 'pack', 'carton', 24, 'Golden Penny'),
    ('ND-PRM-SPA', 'Prima Spaghetti', 'Noodles and pasta', 'pack', 'carton', 24, 'Prima'),
    ('RC-MAM-50', 'Mama Gold Rice 50kg', 'Rice and grains', 'bag', 'bag', 1, 'Mama Gold'),
    ('RC-DAN-50', 'Dangote Rice 50kg', 'Rice and grains', 'bag', 'bag', 1, 'Dangote'),
    ('RC-LOO-RIC', 'Loose Rice (per kg)', 'Rice and grains', 'kg', 'bag', 50, ''),
    ('RC-BEA-1', 'Bean (per kg)', 'Rice and grains', 'kg', 'bag', 50, ''),
    ('OIL-KIN-5L', 'Kings Vegetable Oil 5L', 'Cooking oil and food ingredients', 'bottle', 'carton', 4, 'Kings'),
    ('OIL-EMM-1L', 'Emzor Pure Oil 1L', 'Cooking oil and food ingredients', 'bottle', 'carton', 12, 'Emzor'),
    ('ING-GINO-TOM', 'Gino Tomato Mix', 'Cooking oil and food ingredients', 'sachet', 'carton', 30, 'Gino'),
    ('BVG-COC-50', 'Coca-Cola 50cl', 'Beverages and bottled water', 'bottle', 'crate', 12, 'Coca-Cola'),
    ('BVG-PEP-50', 'Pepsi 50cl', 'Beverages and bottled water', 'bottle', 'crate', 12, 'Pepsi'),
    ('BVG-WAT-75', 'Bottled Water 75cl', 'Beverages and bottled water', 'bottle', 'pack', 12, ''),
    ('SNK-PEP-CHC', 'Peper Chocolate Biscuits', 'Biscuits, snacks and confectionery', 'pack', 'carton', 24, ''),
    ('SNK-SUG-COO', 'Sugar Cookies', 'Biscuits, snacks and confectionery', 'pack', 'carton', 24, ''),
    ('SNK-CHK-BAR', 'Chocolate Bar', 'Biscuits, snacks and confectionery', 'piece', 'box', 48, ''),
    ('MLK-PEA-400', 'Peak Milk Powder 400g', 'Milk and packaged food', 'tin', 'carton', 12, 'Peak'),
    ('MLK-EVA-380', 'Evaporated Milk 380ml', 'Milk and packaged food', 'tin', 'carton', 48, ''),
    ('MLK-MIL-200', 'Milo 200g', 'Milk and packaged food', 'tin', 'carton', 12, 'Milo'),
    ('CLN-ARI-PWD', 'Ariel Washing Powder', 'Household cleaning products', 'sachet', 'carton', 24, 'Ariel'),
    ('CLN-EXC-10', 'Excess 10 Detergent', 'Household cleaning products', 'pack', 'carton', 12, 'Excess'),
    ('CLN-HYP-BLE', 'Hypo Bleach 1L', 'Household cleaning products', 'bottle', 'carton', 12, 'Hypo'),
    ('TIL-DET-500', 'Dettol Antiseptic 500ml', 'Toiletries and personal care', 'bottle', 'carton', 12, 'Dettol'),
    ('TIL-SUN-SOAP', 'Sunlight Soap', 'Toiletries and personal care', 'bar', 'carton', 36, 'Sunlight'),
    ('TIL-ORM-BRS', 'Oral-B Toothbrush', 'Toiletries and personal care', 'piece', 'box', 24, 'Oral-B'),
    ('CAN-COR-BEF', 'Corned Beef 340g', 'Canned and packaged foods', 'tin', 'carton', 24, ''),
    ('CAN-SRD-SAR', 'Sardines 125g', 'Canned and packaged foods', 'tin', 'carton', 48, ''),
    ('CAN-TOM-PAK', 'Tomato Paste 210g', 'Canned and packaged foods', 'tin', 'carton', 24, ''),
]

ZERO = Decimal('0')


class Command(BaseCommand):
    help = 'Seed a realistic supermarket product catalogue. Idempotent. Adds NO stock and NO prices.'

    def handle(self, *args, **options):
        verbosity = int(options.get('verbosity', 1))
        cat_objs = {}
        cats_created = 0
        for cname in CATEGORIES:
            obj, created = ProductCategory.objects.get_or_create(name=cname)
            cat_objs[cname] = obj
            if created:
                cats_created += 1
        prods_created = 0
        prods_skipped = 0
        for sku, name, cat, su, pu, uppu, brand in PRODUCTS:
            _, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': cat_objs[cat],
                    'stock_unit': su,
                    'purchase_unit': pu,
                    'units_per_purchase_unit': Decimal(uppu),
                    'brand': brand,
                    'barcode': '',
                    'unit_price': ZERO,
                    'wholesale_price': ZERO,
                    'current_stock': ZERO,
                    'reorder_level': ZERO,
                    'average_cost': ZERO,
                    'cost_known': False,
                    'is_sample_catalogue': True,
                    'is_active': True,
                    'description': '',
                },
            )
            if created:
                prods_created += 1
            else:
                prods_skipped += 1
        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(
                f'Catalogue seed complete: {cats_created} new categories, {prods_created} new products, '
                f'{prods_skipped} already present (left untouched).'
            ))
            self.stdout.write(self.style.WARNING(
                'No stock and no prices were set. Management must enter real prices and receive goods before sales.'
            ))
