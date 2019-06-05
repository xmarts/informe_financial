# -*- coding: utf-8 -*-

import copy
import ast

from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.tools.misc import formatLang
from odoo.tools import float_is_zero, ustr
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools.pycompat import izip

class ReportAccountFinancialReport(models.Model):
    _description = "Account Report (HTML)"
    _inherit = "account.financial.html.report"

    def _get_columns_name_hierarchy(self, options):
        '''Calculates a hierarchy of column headers meant to be easily used in QWeb.

        This returns a list of lists. An example for 1 period and a
        filter that groups by company and partner:

        [
          [{'colspan': 2, 'name': 'As of 02/28/2018'}],
          [{'colspan': 2, 'name': 'YourCompany'}],
          [{'colspan': 1, 'name': 'ASUSTeK'}, {'colspan': 1, 'name': 'Agrolait'}],
        ]

        The algorithm used to generate this loops through each group
        id in options['groups'].get('ids') (group_ids). E.g. for
        group_ids:

        [(1, 8, 8),
         (1, 17, 9),
         (1, None, 9),
         (1, None, 13),
         (1, None, None)]

        These groups are always ordered. The algorithm loops through
        every first elements of each tuple, then every second element
        of each tuple etc. It generates a header element every time
        it:

        - notices a change compared to the last element (e.g. when processing 17
          it will create a dict for 8) or,
        - when a split in the row above happened

        '''
        if not options.get('groups', {}).get('ids'):
            return False

        periods = [{'string': self.format_date(options), 'class': 'number'}] + options['comparison']['periods']

        # generate specific groups for each period
        groups = []
        for period in periods:
            if len(periods) == 1 and self.debit_credit:
                for group in options['groups'].get('ids'):
                    groups.append(({'string': _('Debit'), 'class': 'number'},) + tuple(group))
                for group in options['groups'].get('ids'):
                    groups.append(({'string': _('Crebit'), 'class': 'number'},) + tuple(group))
            for group in options['groups'].get('ids'):
                groups.append((period,) + tuple(group))

        # add sentinel group that won't be rendered, this way we don't
        # need special code to handle the last group of every row
        groups.append(('sentinel',) * (len(options['groups'].get('fields', [])) + 1))

        column_hierarchy = []

        # row_splits ensures that we do not span over a split in the row above.
        # E.g. the following is *not* allowed (there should be 2 product sales):
        # | Agrolait | Camptocamp |
        # |  20000 Product Sales  |
        row_splits = []

        for field_index, field in enumerate(['period'] + options['groups'].get('fields')):
            current_colspan = 0
            current_group = False
            last_group = False

            # every report has an empty, unnamed header as the leftmost column
            current_hierarchy_line = [{'name': '', 'colspan': 1}]

            for group_index, group_ids in enumerate(groups):
                current_group = group_ids[field_index]
                if last_group is False:
                    last_group = current_group

                if last_group != current_group or group_index in row_splits:
                    current_hierarchy_line.append({
                        #field_index - 1 because ['period'] is not part of options['groups']['fields']
                        'name': last_group.get('string') if field == 'period' else self._get_column_name(last_group, options['groups']['fields'][field_index - 1]),
                     #   'cambio_moneda': last_group.get('string') if field == 'period' else self._get_column_name(last_group, options['groups']['fields'][field_index - 1]),
                        'colspan': current_colspan,
                        'class': 'number',
                    })
                    last_group = current_group
                    current_colspan = 0
                    row_splits.append(group_index)

                current_colspan += 1

            column_hierarchy.append(current_hierarchy_line)

        return column_hierarchy


    #En esta funcion se agregan los nombres de las columnas que se mostraran en el informe financiero, en este caso se agrgo Dolar
    def _get_columns_name(self, options):
        columns = [{'name': ''}]
        if self.debit_credit and not options.get('comparison', {}).get('periods', False):
            columns += [{'name': _('Debit'), 'class': 'number'}, {'name': _('Credit'), 'class': 'number'}]
        columns += [{'name': self.format_date(options) + ' MXN', 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [{'name': period.get('string') + ' MXN', 'class': 'number'}]
            if options['comparison'].get('number_period') == 1 and not options.get('groups'):
                columns += [{'name': '%', 'class': 'number'}]

        if self.debit_credit and not options.get('comparison', {}).get('periods', False):
            columns += [{'name': _('Debit'), 'class': 'number'}, {'name': _('Credit'), 'class': 'number'}]
        columns += [{'name': self.format_date(options) + ' USD', 'class': 'number'}]
        if options.get('comparison') and options['comparison'].get('periods'):
            for period in options['comparison']['periods']:
                columns += [{'name': period.get('string') + ' USD', 'class': 'number'}]


        if options.get('groups', {}).get('ids'):
            columns_for_groups = []
            for column in columns[1:]:
                for ids in options['groups'].get('ids'):
                    group_column_name = ''
                    for index, id in enumerate(ids):
                        column_name = self._get_column_name(id, options['groups']['fields'][index])
                        group_column_name += ' ' + column_name
                    columns_for_groups.append({'name': column.get('name') + group_column_name, 'class': 'number'})
            columns = columns[:1] + columns_for_groups

        return columns

    def _build_options(self, previous_options=None):
        options = super(ReportAccountFinancialReport, self)._build_options(previous_options=previous_options)

        if self.filter_ir_filters:
            options['ir_filters'] = []

            previously_selected_id = False
            if previous_options and previous_options.get('ir_filters'):
                previously_selected_id = [f for f in previous_options['ir_filters'] if f.get('selected')]
                if previously_selected_id:
                    previously_selected_id = previously_selected_id[0]['id']
                else:
                    previously_selected_id = False

            for ir_filter in self.filter_ir_filters:
                options['ir_filters'].append({
                    'id': ir_filter.id,
                    'name': ir_filter.name,
                    #'cambio_moneda': ir_filter.name,
                    'domain': ir_filter.domain,
                    'context': ir_filter.context,
                    'selected': ir_filter.id == previously_selected_id,
                })

        return options

class AccountFinancialReportLine(models.Model):
    _inherit = "account.financial.html.report.line"
    _description = "Account Report (HTML Line)"
    _order = "sequence"
    _parent_store = True

    def _format(self, value):
        if self.env.context.get('no_format'):
            return value
        value['no_format_name'] = value['name']
        if self.figure_type == 'float':
            currency_id = self.env.user.company_id.currency_id
            if currency_id.is_zero(value['name']):
                # don't print -0.0 in reports
                value['name'] = abs(value['name'])
                #value['cambio_moneda'] = abs(value['name'])
                value['class'] = 'number text-muted'
            value['name'] = formatLang(self.env, value['name'], currency_obj=currency_id)
            return value
        if self.figure_type == 'percents':
            value['name'] = str(round(value['name'] * 100, 1)) + '%'
            return value
        value['name'] = round(value['name'], 1)
        return value

      #En divide_line se agrega cambio_moneda para los niveles de la columna
    def _divide_line(self, line):
        line1 = {
            'id': line['id'],
            'name': line['name'],
            #'cambio_moneda': line['name'],
            'class': line['class'],
            'level': line['level'],
            'columns': [{'cambio_moneda': ''}] * len(line['columns']),
            'columns': [{'name': ''}] * len(line['columns']),
            'unfoldable': line['unfoldable'],
            'unfolded': line['unfolded'],
            'page_break': line['page_break'],
        }
        line2 = {
            'id': line['id'],
            #'cambio_moneda': _('Total') + ' ' + line['name'],
            'name': _('Total') + ' ' + line['name'],
            'class': 'total',
            'level': line['level'] + 1,
            'columns': line['columns'],
        }
        return [line1, line2]

    @api.multi
    def _get_lines(self, financial_report, currency_table, options, linesDicts):
        final_result_table = []
        comparison_table = [options.get('date')]
        comparison_table += options.get('comparison') and options['comparison'].get('periods', []) or []
        currency_precision = self.env.user.company_id.currency_id.rounding
        #Variables con valores asignados con dolares y mxn para la conversion
        curr_dols = self.env['res.currency'].search([('name','=','USD')], limit=1)
        curr_mxn = self.env['res.currency'].search([('name','=','MXN')], limit=1)
        # build comparison table
        for line in self:
            res = []
            debit_credit = len(comparison_table) == 1
            domain_ids = {'line'}
            k = 0

            for period in comparison_table:
                date_from = period.get('date_from', False)
                date_to = period.get('date_to', False) or period.get('date', False)
                date_from, date_to, strict_range = line.with_context(date_from=date_from, date_to=date_to)._compute_date_range()

                r = line.with_context(date_from=date_from,
                                      date_to=date_to,
                                      strict_range=strict_range)._eval_formula(financial_report,
                                                                               debit_credit,
                                                                               currency_table,
                                                                               linesDicts[k],
                                                                               groups=options.get('groups'))
                debit_credit = False
                res.extend(r)
                for column in r:
                    domain_ids.update(column)
                k += 1

            res = line._put_columns_together(res, domain_ids)

            if line.hide_if_zero and all([float_is_zero(k, precision_rounding=currency_precision) for k in res['line']]):
                continue

            # Post-processing ; creating line dictionnary, building comparison, computing total for extended, formatting
            vals = {
                'id': line.id,
                'name': line.name,
                #'cambio_moneda': line.name,
                'level': line.level,
                'class': 'o_account_reports_totals_below_sections' if self.env.user.company_id.totals_below_sections else '',
                #Aqui se agrega los datos de la columna y hacer operaciones para mostrarlo en la columna de cambio_moneda
                'columns': [{'name': l, 'cambio_moneda': round(float(self.env['res.currency']._compute(curr_mxn,curr_dols,l)))} for l in res['line']],
                'unfoldable': len(domain_ids) > 1 and line.show_domain != 'always',
                'unfolded': line.id in options.get('unfolded_lines', []) or line.show_domain == 'always',
                'page_break': line.print_on_new_page,
            }

            if financial_report.tax_report and line.domain and not line.action_id:
                vals['caret_options'] = 'tax.report.line'

            if line.action_id:
                vals['action_id'] = line.action_id.id
            domain_ids.remove('line')
            lines = [vals]
            groupby = line.groupby or 'aml'
            if line.id in options.get('unfolded_lines', []) or line.show_domain == 'always':
                if line.groupby:
                    domain_ids = sorted(list(domain_ids), key=lambda k: line._get_gb_name(k))
                for domain_id in domain_ids:
                    name = line._get_gb_name(domain_id)
                    if not self.env.context.get('print_mode') or not self.env.context.get('no_format'):
                        name = name[:40] + '...' if name and len(name) >= 45 else name
                    vals = {
                        'id': domain_id,
                        'name': name,
                        #'cambio_moneda': name,
                        'level': line.level,
                        'parent_id': line.id,
                        'columns': [{'name': l, 'cambio_moneda': round(float(self.env['res.currency']._compute(curr_mxn,curr_dols,l)))} for l in res[domain_id]],
                        'caret_options': groupby == 'account_id' and 'account.account' or groupby,
                        'financial_group_line_id': line.id,
                    }
                    if line.financial_report_id.name == 'Aged Receivable':
                        vals['trust'] = self.env['res.partner'].browse([domain_id]).trust
                    lines.append(vals)
                if domain_ids and self.env.user.company_id.totals_below_sections:
                    lines.append({
                        'id': 'total_' + str(line.id),
                        #'cambio_moneda': _('Total') + ' ' + line.name,
                        'name': _('Total') + ' ' + line.name,
                        'level': line.level,
                        'class': 'o_account_reports_domain_total',
                        'parent_id': line.id,
                        'columns': copy.deepcopy(lines[0]['columns']),
                    })
            for vals in lines:
                if len(comparison_table) == 2 and not options.get('groups'):
                    vals['columns'].append(line._build_cmp(vals['columns'][0]['name'], vals['columns'][1]['name']))
                    for i in [0, 1]:
                        vals['columns'][i] = line._format(vals['columns'][i])
                else:
                    vals['columns'] = [line._format(v) for v in vals['columns']]
                if not line.formulas:
                    vals['columns'] = [{'name': ''} for k in vals['columns']]

            if len(lines) == 1:
                new_lines = line.children_ids._get_lines(financial_report, currency_table, options, linesDicts)
                if new_lines and line.formulas:
                    if self.env.user.company_id.totals_below_sections:
                        divided_lines = self._divide_line(lines[0])
                        result = [divided_lines[0]] + new_lines + [divided_lines[-1]]
                    else:
                        result = [lines[0]] + new_lines
                else:
                    result = lines + new_lines
            else:
                result = lines
            final_result_table += result

        return final_result_table