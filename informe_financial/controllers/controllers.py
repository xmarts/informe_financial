# -*- coding: utf-8 -*-
from odoo import http

# class InformeFinancial(http.Controller):
#     @http.route('/informe_financial/informe_financial/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/informe_financial/informe_financial/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('informe_financial.listing', {
#             'root': '/informe_financial/informe_financial',
#             'objects': http.request.env['informe_financial.informe_financial'].search([]),
#         })

#     @http.route('/informe_financial/informe_financial/objects/<model("informe_financial.informe_financial"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('informe_financial.object', {
#             'object': obj
#         })