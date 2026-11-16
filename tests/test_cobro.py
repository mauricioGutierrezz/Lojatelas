"""Precisión y formatos admitidos para dinero entregado transitorio."""
import unittest
from decimal import Decimal

from app_loja.cobro import efectivo_entregado, format_money
from app_loja.validation import money_input


class CobroInputTests(unittest.TestCase):
    def test_es_ar_and_ungrouped_decimals_without_rounding(self):
        for text,expected in [('10.000','10000'),('25.501,50','25501.50'),
                              ('25501.50','25501.50'),('25501,50','25501.50'),
                              ('0','0'),(' 30.000 ','30000'),('999.999.999.999,99','999999999999.99')]:
            with self.subTest(text=text):
                self.assertEqual(efectivo_entregado(text),Decimal(expected))
        self.assertEqual(format_money(Decimal('25501.50')),'25.501,50')
        self.assertEqual(format_money(Decimal('4498.50')),'4.498,50')

    def test_missing_negative_invalid_precision_and_grouping_are_errors(self):
        for text in (None,'',' ','-1','NaN','Infinity','1,001','1000.001','25.50,10',
                     '25,501.50','1e2','1.000.000.000.000','1,','texto'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                efectivo_entregado(text)

    def test_shared_money_parser_optional_cash_and_two_decimal_presentation(self):
        for raw,expected in (('12500','12500'),('12.500','12500'),
                             ('12.500,50','12500.50'),('12500,50','12500.50')):
            for label in ('Precio inicial','Precio','Fondo inicial','Efectivo contado'):
                with self.subTest(raw=raw,label=label):
                    self.assertEqual(money_input(raw,label,precision=14),Decimal(expected))
            self.assertEqual(efectivo_entregado(raw),Decimal(expected))
        self.assertIsNone(money_input('','Contado',optional=True))
        self.assertEqual(money_input('0','Contado',optional=True),Decimal(0))
        for value,shown in (('26351.25','26.351,25'),('8500.5','8.500,50'),('8500','8.500,00'),
                            ('0','0,00'),('-2501.5','-2.501,50')):
            self.assertEqual(format_money(Decimal(value)),shown)


if __name__=='__main__':
    unittest.main()
