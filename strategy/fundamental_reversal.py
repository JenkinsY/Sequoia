# -*- coding: UTF-8 -*-
import talib as tl
import numpy as np
import akshare as ak
import logging
import datetime

# 综合策略：技术面（下跌趋势反转，突破250日均线）+ 基本面（高ROE，净利润增长，低负债率，高股息率）
def check(code_name, data, end_date=None):
    """
    1. 下跌趋势反转，近几周突破250日均线
    2. ROE高，净利润同比一直增加，或者近几个季度同比净利润由负转正
    3. 资产负债率小于20%，股息率大于3%
    """
    code = code_name[0]
    name = code_name[1]
    
    # 处理结束日期
    if end_date is not None:
        mask = (data['日期'] <= end_date)
        data = data.loc[mask]
    
    # 检查数据量是否足够
    if len(data) < 250:
        logging.debug(f"{code} {name} 数据不足250天，跳过")
        return False
    
    # 1. 技术面分析：下跌趋势反转，突破250日均线
    if not check_ma_breakthrough(data):
        return False
    
    # 2. 基本面分析：ROE、净利润增长
    if not check_financial_growth(code):
        return False
    
    # 3. 基本面分析：资产负债率、股息率
    if not check_financial_ratios(code, data):
        return False
    
    # 所有条件都满足
    logging.info(f"股票 {code} {name} 满足所有条件")
    return True

def check_ma_breakthrough(data):
    """检查是否满足下跌趋势反转，近几周突破250日均线"""
    # 计算250日均线
    data['MA250'] = tl.MA(data['收盘'].values, timeperiod=250)
    
    # 获取最近的数据
    recent_data = data.tail(30)  # 取最近30个交易日
    
    # 检查之前是否处于下跌趋势（以60日均线向下为判断标准）
    data['MA60'] = tl.MA(data['收盘'].values, timeperiod=60)
    downtrend_days = data[-60:-30]  # 取前30-60天的数据
    
    if len(downtrend_days) < 30:
        return False
    
    # 判断之前是否为下跌趋势（MA60向下倾斜）
    ma60_slope = downtrend_days['MA60'].iloc[-1] - downtrend_days['MA60'].iloc[0]
    if ma60_slope >= 0:  # 如果不是下跌趋势，返回False
        return False
    
    # 检查是否突破250日均线
    # 定义突破：之前连续10天都在250日均线下方，最近5天中至少有3天在250日均线上方
    before_break = recent_data.iloc[:-5]
    after_break = recent_data.iloc[-5:]
    
    if len(before_break) < 10 or len(after_break) < 5:
        return False
    
    # 检查之前是否连续在均线下方
    below_ma250_before = sum(before_break.iloc[-10:]['收盘'] < before_break.iloc[-10:]['MA250'])
    if below_ma250_before < 8:  # 允许有2天的误差
        return False
    
    # 检查最近是否有足够的天数在均线上方
    above_ma250_after = sum(after_break['收盘'] > after_break['MA250'])
    if above_ma250_after < 3:
        return False
    
    # 检查成交量是否放大
    avg_volume_before = before_break['成交量'].mean()
    avg_volume_after = after_break['成交量'].mean()
    if avg_volume_after <= avg_volume_before:
        return False
    
    return True

def check_financial_growth(code):
    """检查ROE和净利润增长情况"""
    try:
        # 获取财务指标数据
        financial_data = ak.stock_financial_analysis_indicator(symbol=code)
        if financial_data is None or financial_data.empty:
            logging.debug(f"{code} 无法获取财务数据")
            return False
        
        # 获取最近的ROE数据
        if '净资产收益率(%)' in financial_data.columns:
            recent_roe = financial_data['净资产收益率(%)'].iloc[0]
            if recent_roe < 10:  # ROE至少10%
                return False
        else:
            logging.debug(f"{code} 缺少ROE数据")
            return False
        
        # 获取利润表数据
        profit_data = ak.stock_financial_report_sina(symbol=code, report_type="利润表")
        if profit_data is None or profit_data.empty:
            logging.debug(f"{code} 无法获取利润表数据")
            return False
        
        # 获取最近几个季度的净利润数据
        if '净利润' in profit_data.columns:
            # 获取最近4个季度的净利润
            recent_profits = profit_data['净利润'].head(4).values
            if len(recent_profits) < 4:
                return False
            
            # 检查净利润是否增长或由负转正
            profit_increasing = True
            profit_turning_positive = False
            
            # 检查是否连续增长
            for i in range(len(recent_profits) - 1):
                if recent_profits[i] <= recent_profits[i+1]:  # 净利润应该是时间倒序排列的
                    profit_increasing = False
            
            # 检查是否由负转正
            if recent_profits[3] < 0 and recent_profits[0] > 0:  # 最早的是负的，最近的是正的
                profit_turning_positive = True
            
            if not (profit_increasing or profit_turning_positive):
                return False
        else:
            logging.debug(f"{code} 缺少净利润数据")
            return False
        
        return True
    
    except Exception as e:
        logging.error(f"获取 {code} 财务数据时出错: {str(e)}")
        return False

def check_financial_ratios(code, data):
    """检查资产负债率和股息率"""
    try:
        # 获取资产负债率数据
        balance_data = ak.stock_financial_analysis_indicator(symbol=code)
        if balance_data is None or balance_data.empty:
            logging.debug(f"{code} 无法获取资产负债率数据")
            return False
        
        # 检查资产负债率
        if '资产负债率(%)' in balance_data.columns:
            debt_ratio = balance_data['资产负债率(%)'].iloc[0]
            if debt_ratio > 20:  # 资产负债率需要小于20%
                return False
        else:
            logging.debug(f"{code} 缺少资产负债率数据")
            return False
        
        # 获取股息率数据
        try:
            dividend_data = ak.stock_history_dividend_detail(symbol=code)
            if dividend_data is None or dividend_data.empty:
                logging.debug(f"{code} 无法获取股息数据")
                return False
            
            # 计算最近一年的股息率
            current_year = datetime.datetime.now().year
            recent_dividends = dividend_data[dividend_data['年份'] >= (current_year - 1)]
            
            if len(recent_dividends) == 0:
                return False
            
            # 获取最新股价
            latest_price = None
            try:
                stock_info = ak.stock_zh_a_spot_em()
                stock_info = stock_info[stock_info['代码'] == code]
                if not stock_info.empty:
                    latest_price = stock_info['最新价'].iloc[0]
            except:
                pass
            
            if latest_price is None:
                latest_price = data.iloc[-1]['收盘']  # 使用历史数据中的最新收盘价
            
            # 计算股息率
            total_dividend = recent_dividends['分红金额(元)'].sum()
            dividend_yield = (total_dividend / latest_price) * 100
            
            if dividend_yield < 3:  # 股息率需要大于3%
                return False
            
        except Exception as e:
            logging.error(f"获取 {code} 股息数据时出错: {str(e)}")
            return False
        
        return True
    
    except Exception as e:
        logging.error(f"检查 {code} 财务比率时出错: {str(e)}")
        return False 