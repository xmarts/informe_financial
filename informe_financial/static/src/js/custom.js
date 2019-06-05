
odoo.define('account_reports.account_reports', function(require) {
"use strict";

Class = require('web.Class');
mixins = require('web.mixins');

var DataSet = Class.extend(mixins.PropertiesMixin, {
    name_search: function (name, domain, operator, limit) {
        /* Custom code to override/extend core */
    },
});

return {
    DataSet: DataSet,
};

});