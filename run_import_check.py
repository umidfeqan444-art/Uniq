import import_sellers_fixed
print('module:', import_sellers_fixed.__file__, flush=True)
print('has get_country_page:', hasattr(import_sellers_fixed, 'get_country_page'), flush=True)
names = [n for n in dir(import_sellers_fixed) if not n.startswith('_')]
print('names count:', len(names), flush=True)
print('sample names:', names[:40], flush=True)
