
NAMESPACES = {
    'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
    'bs': 'http://api.vetrf.ru/schema/cdm/base',
    'dt': 'http://api.vetrf.ru/schema/cdm/dictionary/v2',
    'ws': 'http://api.vetrf.ru/schema/cdm/registry/ws-definitions/v2',
    'merc': 'http://api.vetrf.ru/schema/cdm/mercury/g2b/applications/v2',
    'apldef': 'http://api.vetrf.ru/schema/cdm/application/ws-definitions',
    'apl': 'http://api.vetrf.ru/schema/cdm/application',
    'vd': 'http://api.vetrf.ru/schema/cdm/mercury/vet-document/v2',
}

# PROD
# ENDPOINTS = {
#     'ProductService': 'https://api.vetrf.ru/platform/services/2.1/ProductService',
#     'EnterpriseService': 'https://api.vetrf.ru/platform/services/2.1/EnterpriseService',
# }

# TEST
ENDPOINTS = {
    'ProductService': 'https://api2.vetrf.ru:8002/platform/services/2.1/ProductService',
    'EnterpriseService': 'https://api2.vetrf.ru:8002/platform/services/2.1/EnterpriseService',
}