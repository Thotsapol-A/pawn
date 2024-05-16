# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
import ast


class item_split(osv.osv_memory):

    _name = "item.split"
    _description = "Split Item"

    def _get_item_id(self, cr, uid, context=None):
        if context is None:
            context = {}
        return context.get('active_id', False)

    _columns = {
        'item_id': fields.many2one('product.product', 'Product', readonly=True),
        'split_line': fields.one2many('item.split.line', 'item_id', 'Split Lines', readonly=False),
    }
    _defaults = {
        'item_id': _get_item_id,
    }

    def _validate_line_before_split_item(self, cr, uid, ids, context=None):
        wizard = self.browse(cr, uid, ids[0], context=context)
        item = wizard.item_id
        new_qty = 0.0
        new_total_price_estimated = 0.0
        new_total_price_pawned = 0.0
        new_carat = 0.0
        new_gram = 0.0
        for line in wizard.split_line:
            # Check item quantity > 0
            if line.product_qty <= 0:
                raise osv.except_osv(_('Warning!'), _('Item quantity must greater than zero'))
            # Check total pawned price > 0
            if line.total_price_pawned <= 0:
                raise osv.except_osv(_('Warning!'), _('Total pawned price must greater than zero'))
            # Check total estimated price > 0
            if line.total_price_estimated <= 0:
                raise osv.except_osv(_('Warning!'), _('Total estimated price must greater than zero'))
            # Sum qty, total price
            new_qty += line.product_qty
            new_total_price_estimated += line.total_price_estimated
            new_total_price_pawned += line.total_price_pawned
            # Sum carat, gram
            new_carat += line.carat
            new_gram += line.gram
        # Check lines >= 2 lines when split
        if len(wizard.split_line) < 2:
            raise osv.except_osv(_('Warning!'), _('At least 2 split line must be created!'))
        # Check total quantity must equal to original
        if new_qty != item.product_qty:
            raise osv.except_osv(_('Warning!'), _('Sum of quantity must equal to the original quantity'))
        # Check total pawned price must equal to original
        if new_total_price_pawned != item.total_price_pawned:
            raise osv.except_osv(_('Warning!'), _('Sum of total pawned price must equal to the original total pawned price'))
        # Check total estimated price must equal to original
        if new_total_price_estimated != item.total_price_estimated:
            raise osv.except_osv(_('Warning!'), _('Sum of total estimated price must equal to the original total estimated price'))
        # Check total carat must equal to original
        if new_carat != item.carat:
            raise osv.except_osv(_('Warning!'), _('Sum of total carat must equal to the original total carat'))
        # Check total gram must equal to original
        if new_gram != item.gram:
            raise osv.except_osv(_('Warning!'), _('Sum of total gram must equal to the original total gram'))
        return True

    def create(self, cr, uid, vals, context=None):
        item_split_id = super(item_split, self).create(cr, uid, vals, context=context)
        self._validate_line_before_split_item(cr, uid, [item_split_id], context=context)
        return item_split_id

    def write(self, cr, uid, ids, vals, context=None):
        res = super(item_split_line, self).write(cr, uid, ids, vals, context=context)
        self._validate_line_before_split_item(cr, uid, ids, context=context)
        return res

    def open_items(self, cr, uid, item_ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        result = mod_obj.get_object_reference(cr, uid, 'pawnshop', 'action_pawn_items_for_sale')
        id = result and result[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        domain = ast.literal_eval(result['domain'])
        domain.append(('id', 'in', item_ids))
        result['domain'] = domain
        result['name'] = _('Items For Sales')
        return result

    def action_split(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.browse(cr, uid, ids[0], context=context)
        item = wizard.item_id

        # Start coping and redirecton
        item_obj = self.pool.get('product.product')
        cur_obj = self.pool.get('res.currency')
        cur = item.order_id.pricelist_id.currency_id
        i = 0
        new_item_ids = []
        for line in wizard.split_line:
            i += 1
            default = {
                'product_qty': line.product_qty,
                'carat': line.carat,
                'gram': line.gram,
                'price_estimated': cur_obj.round(cr, uid, cur, line.total_price_estimated / line.product_qty),
                'total_price_estimated': line.total_price_estimated,
                'price_pawned': cur_obj.round(cr, uid, cur, line.total_price_pawned / line.product_qty),
                'total_price_pawned': line.total_price_pawned,
                'description': line.description,
                'journal_id': item.journal_id.id,
            }
            new_item_id = item_obj.copy(cr, uid, item.id, default, context=context)
            item_obj.write(cr, uid, [new_item_id], {'name': item.name + '.' + str(i)}, context=context)
            new_item_ids.append(new_item_id)
        # Inactive old item
        item_obj.write(cr, uid, [item.id], {'active': False})
        return self.open_items(cr, uid, new_item_ids, context=context)


item_split()


class item_split_line(osv.osv_memory):

    _name = "item.split.line"
    _description = "Item Split Line"

    def _get_description(self, cr, uid, context=None):
        if context is None:
            context = {}
        active_id = context.get('active_id', False)
        if active_id:
            item = self.pool.get('product.product').browse(cr, uid, active_id, context=context)
            return item.description or False
        return False

    _columns = {
        'item_id': fields.many2one('item.split', 'Item Split'),
        'description': fields.text('Description', required=True),
        'product_qty': fields.float('Item Quantity', required=True),
        'carat': fields.float('Carat'),
        'gram': fields.float('Gram'),
        'total_price_estimated': fields.float('Total Estimated Price', required=True),
        'total_price_pawned': fields.float('Total Pawned Price', required=True),
    }
    _defaults = {
        'description': _get_description,
        'product_qty': 0.0,
        'total_price_estimated': 0.0,
        'total_price_pawned': 0.0,
    }

    def onchange_total_price_pawned(self, cr, uid, ids, total_price_pawned, context=None):
        # Not used estimated price now so we define estimated price = pawned price
        return {'value': {'total_price_estimated': total_price_pawned}}


item_split_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
