from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from focas_engine.config import HARD_DATA_SOURCE


def _write_corrected_table(path: Path) -> str:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    headers = [
        "体系",
        "区间",
        "档位差",
        "让球",
        "水位",
        "主赔_骨架精确",
        "平赔_机构档口参考",
        "负赔_机构档口参考",
        "返回率_参考组合",
        "主赔来源",
        "平负来源",
        "校验状态",
        "精确查表权限",
        "分析使用方式",
        "P5输出规则",
        "P8边界规则",
    ]
    water_offsets = (("高水", 0.04), ("中水", 0.0), ("低水", -0.04))
    for system in range(89, 97):
        sheet = workbook.create_sheet(f"{system}体系")
        sheet.append([f"{system}体系｜测试现代主赔骨架区间表"])
        sheet.append(headers)
        for interval in range(9):
            for water, offset in water_offsets:
                main_price = round(2.70 - interval * 0.16 + offset + (system - 94) * 0.01, 3)
                sheet.append([
                    f"{system}体系",
                    f"{interval}区",
                    "测试档位",
                    "测试让球",
                    water,
                    main_price,
                    3.20,
                    3.40,
                    None,
                    "MAIN_PRICE_CORE_PRECISE",
                    "MARKET_LADDER_REFERENCE",
                    "PASS",
                    "仅主赔允许精确查表",
                    "按体系 sheet 查表",
                    "输出区间和水位",
                    "输出边界距离",
                ])
    workbook.save(path)
    return str(path)


@pytest.fixture()
def mini_table(tmp_path):
    return _write_corrected_table(tmp_path / "corrected_market_ladder.xlsx")


@pytest.fixture()
def default_corrected_table(tmp_path):
    return _write_corrected_table(tmp_path / HARD_DATA_SOURCE)
