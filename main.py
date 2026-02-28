### 导入库
# 核心转换，将end_time变成day变量

import pandas as pd 
import numpy as np
import pymysql
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
plt.rcParams['axes.unicode_minus']=False #用来正常显示负号
import datetime
from datetime import  timedelta
from fbprophet import Prophet
from pyecharts.charts import *
from pyecharts.components import Table
from pyecharts import options as opts
from pyecharts.commons.utils import JsCode
import random
import datetime
import pyecharts
# pyecharts.globals._WarningControl.ShowWarning = False
from pyecharts.render import make_snapshot
from snapshot_selenium import snapshot
import smtplib
import email
# 负责构造文本
from email.mime.text import MIMEText
# 负责构造图片
from email.mime.image import MIMEImage
# 负责将多个对象集合起来
from email.mime.multipart import MIMEMultipart
from email.header import Header

# mysql取数
def mysql_datagain(day):
    '''
    目的：从mysql中取数明细数据
    day：时间，例'2021-02-23'
    '''
    db = pymysql.connect(host='127.0.0.1',port=3306,user='root',password='123456',db='report',charset='utf8')
    cursor =db.cursor()
    start_time = (datetime.datetime.strptime(day,'%Y-%m-%d') - timedelta(days=22)).strftime('%Y-%m-%d')
    sql = '''select * from sp_karate_detail where day between %s and %s'''
    cursor.execute(sql,(start_time,day))
    data = cursor.fetchall()
    col = [i[0] for 
           i in cursor.description]
    df = pd.DataFrame(list(data),columns=col)
    db.close()
    return df

# python数据清洗

def dataprocess(df):
    '''
    目的：数据类型转换，按天聚合
    df：明细数据
    '''
    
    df['ka_people'] = df['ka_people'].astype(np.float).astype(int)
    df['all_people'] = df['all_people'].astype(np.float).astype(int)
    
    df_kpi = df.groupby('day',as_index=False)[['ka_people','all_people']].sum()
    df_kpi['ka_rate']  = df_kpi['ka_people'] / df_kpi['all_people']
    return df_kpi

# 异常检测算法判断异常
def prophet_error(df,day):
    '''
    目的：判断当天卡顿率是否异常
    
    df : 明细数据
    day : 时间，例'2021-02-23'
    '''
    #转换成prophet所需格式
    df = df[['day','ka_rate']]
    df.columns = ['ds','y']
    
    
    #神经网络prophet修改后
    m = NeuralProphet(
    n_forecasts=1,
    yearly_seasonality=False,
    weekly_seasonality=False,
    daily_seasonality=False,
    epochs=100)

metrics = m.fit(df, freq='D')
forecast = m.predict(df)
# --- 3. 异常点检测逻辑 ---
# 计算残差 (实际值与预测值的绝对差)
forecast['residual'] = (forecast['y'] - forecast['yhat1']).abs()
# 设定动态阈值：均值 + 2倍标准差 (Sigma原则)
threshold = forecast['residual'].mean() + 2 * forecast['residual'].std()
forecast['is_outlier'] = forecast['residual'] > threshold
# 筛选异常点明细
outliers = forecast[forecast['is_outlier']].copy()
outlier_dates = outliers['ds'].dt.strftime('%Y-%m-%d').tolist()

    

    result = 1 if day in outlier_dates else 0 
    return result

# 多维度下钻分析 - 文字
def analyse_textmake(df,day):
    '''
    目的：构建邮件日报的文字
    df：明细数据
    day：时间，例'2021-02-23'
    '''
    df = dataprocess(df)
    # 日期
    
    # 各天卡顿率
    today_karate = round(df[df['day']==day]['ka_rate'].values[0],4)
    yesterday = (datetime.datetime.strptime(day,'%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    last7day = (datetime.datetime.strptime(day,'%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
    yesterday_karate = round(df[df['day']==yesterday]['ka_rate'].values[0],4)
    last7day_karate = round(df[df['day']==last7day ]['ka_rate'].values[0],4)
    
    # 相比昨天环比{上升/下降/持平}xxx%
    yesterday_dif = []
    if today_karate <= yesterday_karate:
        yes_text = '下降'
        yesterday_dif.append(round((yesterday_karate - today_karate)*100/yesterday_karate,2))

    elif today_karate >= yesterday_karate:
        yes_text = '上升'
        yesterday_dif.append(round((today_karate-yesterday_karate)*100/yesterday_karate,2))
    else:
        yes_text = '持平'
        yesterday_dif.append('')
        
    # 相比上周同比{上升/下降/持平}xxx%
    last7day_dif = []
    if today_karate <= last7day_karate:
        last7d_text = '下降'
        last7day_dif.append(round((last7day_karate - today_karate)*100/last7day_karate,2))
    elif today_karate >= yesterday_karate:
        last7d_text = '上升'
        last7day_dif.append(round((today_karate-last7day_karate)*100/last7day_karate,2))
    else:
        last7d_text = '持平'
        last7day_dif.append('')
    
    # Text制作
    text = "今天是{}，当天业务核心指标卡顿率为{}，相比昨天环比{}{}%，相比上周同比{}{}%，详细数据可看以下图表。".format(day,str(today_karate*100)+"%",yes_text,yesterday_dif[0],last7d_text,last7day_dif[0])
    return text

# 多维度下钻分析 - 图表
def analyse_tablemake(df,day):
    '''
    目的：构建邮件日报的CDN质量排名表格
    df：明细数据
    day：时间，例'2021-02-23'
    '''
    df_today = df[df['day']==day]
    df_cdn = df_today.groupby('cdn_name',as_index=False)[['ka_people','all_people']].sum()
    df_cdn['ka_rate'] = df_cdn['ka_people'] / df_cdn['all_people']
    df_cdn['rank'] = df_cdn['ka_rate'].rank().astype(int)
    df_cdn['ka_rate'] = round(df_cdn['ka_rate']*100,2).astype(str) +'%'
    df_cdn.columns = ['cdn','卡顿人数','观众总人数','卡顿率','质量排名']
    return df_cdn

# 多维度下钻分析 - 图片
def analyse_picturemake(df,day):
    '''
    目的：构建邮件日报的图表
    df：明细数据
    day：异常时间点
    '''

    
    rich_text = {
        "a": {"color": "#999", "lineHeight": 22, "align": "center"},
        "abg": {
            "backgroundColor": "#e3e3e3",
            "width": "100%",
            "align": "right",
            "height": 22,
            "borderRadius": [4, 4, 0, 0],
        },
        "hr": {
            "borderColor": "#aaa",
            "width": "100%",
            "borderWidth": 0.5,
            "height": 0,
        },
        "b": {"fontSize": 16, "lineHeight": 33},
        "per": {
            "color": "#eee",
            "backgroundColor": "#334455",
            "padding": [2, 4],
            "borderRadius": 2,
        },
    }
    
    df_kpi = dataprocess(df)
    
    # 近20天卡顿率趋势图
    x_data = list(df_kpi['day'])
    y_data = list(df_kpi['ka_rate'].round(3))
    line = Line(init_opts=opts.InitOpts(theme='light',bg_color=JsCode(bg_color_js),width='700px',height='350px'))
    line.add_xaxis(x_data)
    line.add_yaxis('卡顿率',y_data)
    line.set_series_opts(label_opts=opts.LabelOpts(is_show=False),itemstyle_opts=opts.ItemStyleOpts(color='red',border_color='black'),
                        markarea_opts=opts.MarkAreaOpts(data=[opts.MarkAreaItem(name="春节", x=("2021-02-11","2021-02-18"))]))
    line.set_global_opts(legend_opts=opts.LegendOpts(is_show=False),title_opts=opts.TitleOpts(title="近20天卡顿率趋势图"))
    make_snapshot(snapshot,line.render(),"1.png")
    
    # 近20天总人数与卡顿人数联合表
    y_data1 = list(df_kpi['ka_people'])
    y_data2 = list(df_kpi['all_people'])
    bar = Bar(init_opts=opts.InitOpts(theme='light', bg_color=JsCode(bg_color_js),width='700px', height='350px'))
    bar.add_xaxis(x_data)
    bar.add_yaxis('观看总人数', y_data1)
    bar.add_yaxis('卡顿总人数', y_data2)
    bar.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    bar.set_global_opts(title_opts=opts.TitleOpts(title="近20天观看&卡顿总人数"),legend_opts=opts.LegendOpts(pos_right=10))
    make_snapshot(snapshot,bar.render(),"2.png")
    
    # 当天各平台观众分布
    df_today = df[df['day']==day]
    df_plat_pie = df_today.groupby('user_plat',as_index=False)['all_people'].sum()
    x_plat_data = list(df_plat_pie ['user_plat'])
    y_plat_data = list(df_plat_pie ['all_people'])
    pie_plat = (Pie(init_opts=opts.InitOpts(theme='infographic',bg_color=JsCode(bg_color_js),width='700px', height='350px'))
       .add('观众人数', [list(z) for z in zip(x_plat_data, y_plat_data)],
       label_opts=opts.LabelOpts(
                     formatter="\n\n\n{a|{a}}{abg|}\n{hr|}\n {b|{b}: }{c}\n{per|{d}%}    ",
                     rich=rich_text))
       )
    pie_plat.set_global_opts(title_opts=opts.TitleOpts(title="%s各平台观众分布"%day),legend_opts=opts.LegendOpts(pos_right=10))
    make_snapshot(snapshot,pie_plat.render(),"3.png")
    
    # 当天各isp观众分布
    df_isp_pie = df_today.groupby('isp',as_index=False)['all_people'].sum()
    x_isp_data = df_isp_pie['isp']
    y_isp_data = df_isp_pie['all_people']
    pie_isp = (Pie(init_opts=opts.InitOpts(theme='essos',bg_color=JsCode(bg_color_js),width='700px', height='350px'))
       .add('观众人数', [list(z) for z in zip(x_isp_data, y_isp_data)],
       label_opts=opts.LabelOpts(position='outsiede',
                     formatter="\n\n\n\n\n\n{a|{a}}{abg|}\n{hr|}\n       {b|{b}: }{c}  {per|{d}%}       ",
                     rich=rich_text))
       )
    pie_isp.set_global_opts(title_opts=opts.TitleOpts(title="%s各运营商观众分布"%day),legend_opts=opts.LegendOpts(pos_right=10))
    make_snapshot(snapshot,pie_isp.render(),"4.png")
    
    # 当天各省份观众人数
    df_prov = df_today.groupby('province',as_index=False)['all_people'].sum()
    df_prov = df_prov.sort_values('all_people')
    x_data = list(df_prov['province'])
    y_data = list(df_prov['all_people'])
    bar2 = Bar(init_opts=opts.InitOpts(theme='roma', bg_color=JsCode(bg_color_js),width='700px', height='350px'))
    bar2.add_xaxis(x_data)
    bar2.add_yaxis('观看总人数', y_data)
    bar2.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
    bar2.set_global_opts(title_opts=opts.TitleOpts(title="%s各省份观看人数"%day),legend_opts=opts.LegendOpts(is_show=False))
    bar2.reversal_axis()
    make_snapshot(snapshot,bar2.render(),"5.png")
    
# html+css制作汇报内容
def generate_html(raw_html):
    '''
    目的：构建CDN质量排名表格html框架和字段名
    raw_html：generate_table()函数后的数据
    '''
    html = """
    <style type="text/css">
    .tg  {border-collapse:collapse;border-color:#93a1a1;border-spacing:0;}
    .tg td{background-color:#fdf6e3;border-color:#93a1a1;border-style:solid;border-width:1px;color:#002b36;
      font-family:Arial, sans-serif;font-size:14px;overflow:hidden;padding:10px 5px;word-break:normal;}
    .tg th{background-color:#657b83;border-color:#93a1a1;border-style:solid;border-width:1px;color:#fdf6e3;
      font-family:Arial, sans-serif;font-size:14px;font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
    .tg .tg-pb0m{border-color:inherit;text-align:center;vertical-align:bottom}
    .tg .tg-9wq8{border-color:inherit;text-align:center;vertical-align:middle}
    .tg .tg-td2w{border-color:inherit;font-size:20px;font-weight:bold;text-align:center;vertical-align:middle}
    .tg .tg-c3ow{border-color:inherit;text-align:center;vertical-align:top}
    .tg .tg-vd9z{background-color:#fe0000;border-color:inherit;color:#f8ff00;font-weight:bold;text-align:center;vertical-align:top}
    </style>
    
    <table class="tg">
    <thead>
      <tr>
        <th class="tg-td2w">cdn</th>
        <th class="tg-td2w">卡顿人数</th>
        <th class="tg-td2w">观众总人数</th>
        <th class="tg-td2w">卡顿率</th>
        <th class="tg-td2w">质量排名</th>
      </tr>
    </thead>
    <tbody>
    
     """+ raw_html +"""
    <tbody>
    </table>
    """ 
    return html

def generate_table(data):
    '''
    目的：将CDN质量排名表格dataframe的数据转换为html
    data：CDN质量排名表格dataframe
    '''
    html = ''
    for index in range(data.shape[0]):
        # 选取行的索引，一行一行建设
        html += '<tr>'
        for col in range(data.shape[1]):
            # 选取列的索引，一列一列的填入
            if col==3:
            # 如果col，列索引为3的时候
                if np.float(data.iloc[index,3].strip('%')) >=10:
                # 如何卡顿率>=10
                    html += '<td class="tg-vd9z">'+ str(data.iloc[index,col]) + '</td>'
                else:
                    html += '<td class="tg-9wq8">'+ str(data.iloc[index,col]) + '</td>'
            else:
                html += '<td class="tg-9wq8">'+ str(data.iloc[index,col]) + '</td>'
        html += '</tr>'
    return html  


# 根因定位报表
def generate_html_reason(raw_html):
    '''
    目的：构建根因定位表格html框架和字段名
    raw_html：generate_table_reason()函数后的数据
    '''
    html = """
    <style type="text/css">
    .tg  {border-collapse:collapse;border-color:#93a1a1;border-spacing:0;}
    .tg td{background-color:#fdf6e3;border-color:#93a1a1;border-style:solid;border-width:1px;color:#002b36;
      font-family:Arial, sans-serif;font-size:14px;overflow:hidden;padding:10px 5px;word-break:normal;}
    .tg th{background-color:#657b83;border-color:#93a1a1;border-style:solid;border-width:1px;color:#fdf6e3;
      font-family:Arial, sans-serif;font-size:14px;font-weight:normal;overflow:hidden;padding:10px 5px;word-break:normal;}
    .tg .tg-pb0m{border-color:inherit;text-align:center;vertical-align:bottom}
    .tg .tg-9wq8{border-color:inherit;text-align:center;vertical-align:middle}
    .tg .tg-td2w{border-color:inherit;font-size:20px;font-weight:bold;text-align:center;vertical-align:middle}
    .tg .tg-c3ow{border-color:inherit;text-align:center;vertical-align:top}
    .tg .tg-vd9z{background-color:#fe0000;border-color:inherit;color:#f8ff00;font-weight:bold;text-align:center;vertical-align:top}
    </style>
    
    <table class="tg">
    <thead>
      <tr>
        <th class="tg-td2w">维度</th>
        <th class="tg-td2w">条件</th>
        <th class="tg-td2w">卡顿人数</th>
        <th class="tg-td2w">总人数</th>
        <th class="tg-td2w">该条件下卡顿率</th>
        <th class="tg-td2w">全网卡顿率</th>
        <th class="tg-td2w">该条件影响度</th>
        <th class="tg-td2w">去掉该条件数据后卡顿率</th>
        <th class="tg-td2w">根因排序</th>
      </tr>
    </thead>
    <tbody>
    
     """+ raw_html +"""
    <tbody>
    </table>
    """ 
    return html

def generate_table_reason(data):
    '''
    目的：将根因定位表格dataframe的数据转换为html
    data：根因定位表格dataframe
    '''
    html = ''
    for index in range(data.shape[0]):

        html += '<tr>'
        for col in range(data.shape[1]):
            html += '<td class="tg-9wq8">'+ str(data.iloc[index,col]) + '</td>'
        html += '</tr>'
    return html  

# 根因定位算法
def yxd_rootcause_function(data,columns,day):
    
    '''
    目的：找出异常的根因
    data：明细数据
    columns：根因定位维度
    day：哪个时间段fsd
    '''
    
    data = data[data['day']==day]
    data = data.groupby(columns,as_index=False)[['ka_people','all_people']].sum()
    data['ka_rate'] = data['ka_people']/data['all_people']
    data['value_all'] = data['ka_people'].sum()
    data['cnt_all'] = data['all_people'].sum()
    data['cnt_all'] = data['all_people'].sum()
    data['rate_all'] = data['value_all']/data['cnt_all']
    data['yxd'] = data['rate_all'] - (data['value_all'] - data['ka_people'])/(data['cnt_all']-data['all_people'])
    data['rate_del'] = data['rate_all'] - data['yxd']
    data = data.sort_values('yxd',ascending=False)
    data['colname']= columns
    data.columns = ['factor','ka_people', 'all_people', 'ka_rate', 'value_all','cnt_all', 'rate_all', 'yxd', 'rate_del', 'colname']
    data = data[['colname','factor','ka_people', 'all_people', 'ka_rate', 'value_all','cnt_all', 'rate_all', 'yxd', 'rate_del']]
    return data

# 根因定位数据处理
def rootdata_deal(data,col,value):
    '''
    目的：
    data：df
    col：维度
    value：条件
    
    '''
    data = data[data[col]!=value]
    
    data = data.groupby('day',as_index=False)[['ka_people','all_people']].sum()
    data['%s_ka_rate'%col] = data['ka_people']/data['all_people']
    data = data[['day','%s_ka_rate'%col]]
    return data

# 邮件msg制作
def msg_make(df,day,text):
    '''
    目的：将智能日报展现的所有内容封装成msg
    df:明细数据df
    day：异常时间点
    text：analyse_textmake输出的文字
    '''
    
    
    # 创建邮件对象
    msg = MIMEMultipart()
    # 添加邮件头部内容
    subject_content = "%s卡顿率智能数据监控邮件日报"%day
    msg['Subject'] = Header(subject_content,'utf-8')
    # 发件人
    msg['From'] = mail_sender
    # 收件人
    msg['To'] = ",".join(to_list)
    # 抄送人
    msg['cc'] = ",".join(ccto_list)
    
    # 添加正文
    # 文字
    text_html = "<h2>" + text + "</h2>"
    
    # 表格
    df_cdn = analyse_tablemake(df,day)
    table_html = generate_html(generate_table(df_cdn))
    context = MIMEText(text_html+table_html,_subtype='html',_charset='utf-8')
    msg.attach(context)
    
    # 图片
    for num in range(1,6):
        picture_html = MIMEText('<br/><html><body><img src="cid:image%s"></body></html><br/>'%num,'html','utf-8')
        msg.attach(picture_html)
        msgImage = MIMEImage(open('%s.png'%num, 'rb').read())
        msgImage.add_header('Content-ID','image%s'%num)
        msg.attach(msgImage)
    
    # 附件
    df_today = df[df['day']==day]
    df_today.to_csv('att.csv',index=False,encoding='gbk')
    att = MIMEText(open('att.csv','rb').read(),'base64','gb2312')
    att['Content-Type'] = 'application/octet-stream'
    att["Content-Disposition"] = 'attachment;filename="%sdata_detail.csv"'%day
    msg.attach(att)
    
    if prophet_error(dataprocess(df),day)==1:
        # 根因定位报表 - 标题
        rc_title ='''<h1 style="background-color:#00009b;border-color:inherit;color:#ffffff;font-weight:bold;text-align:left;vertical-align:top">智能根因定位日报</h1>'''
        context_rc = MIMEText(rc_title,_subtype='html',_charset='utf-8')
        msg.attach(context_rc)
        
        # 根因定位报表 - 文字 + 表格
        
        # 当天卡顿率 
        df_kpi = dataprocess(df)
        today_karate = round(df_kpi[df_kpi['day']==day]['ka_rate'].values[0],4)
        
        # 根因定位算法运用
        reason_list = list(df.columns[1:6])
        
        data_list =[]
        for columns in reason_list:
            data_list.append(yxd_rootcause_function(df,columns,day))
        df_c = pd.concat(data_list)
        df_c = df_c.sort_values('yxd',ascending=False)
        df_reason = df_c.iloc[:3]
        df_reason = df_reason[['colname','factor','ka_people','all_people','ka_rate','rate_all','yxd','rate_del']]
        df_reason.columns = ['维度','条件','卡顿人数','总人数','该条件下卡顿率','全网卡顿率','该条件影响度','去掉该条件数据后卡顿率']
        df_reason['根因排序'] = ['Top1','Top2','Top3']
        for i in ['该条件下卡顿率','全网卡顿率','该条件影响度','去掉该条件数据后卡顿率']:
            df_reason[i] = (df_reason[i]*100).round(2).astype(str) +'%'
        
        rc_text = '''
        <style type="text/css">
        tg-bx2p{background-color:#036400;color:#ffffff;font-size:24px;font-weight:bold;}
        tg-s6o7{border-color:inherit;color:#fe0000;font-size:24px;font-weight:bold;text-align:center;vertical-align:bottom}
        </style>
        
        
        <h2>我们基于<tg-s6o7>Prophet时间序列异常检测算法</tg-s6o7>发现当天(%s)的卡顿率(<tg-s6o7>%s</tg-s6o7>)为异常值，调用<tg-s6o7>基于影响度的根因定位算法</tg-s6o7>分析出以下几种根因可能是引起异常的关键点，麻烦相关业务同学进一步核实。</h2>
        '''%(day,str(today_karate*100)+'%')
        
        reason_html = generate_html_reason(generate_table_reason(df_reason))
        context_rctext = MIMEText(rc_text+reason_html,_subtype='html',_charset='utf-8')
        msg.attach(context_rctext)
        
        # 根因定位报表 - 图表
        
        df_top1 = rootdata_deal(df,df_reason['维度'].iloc[0],df_reason['条件'].iloc[0])
        df_top2 = rootdata_deal(df,df_reason['维度'].iloc[1],df_reason['条件'].iloc[1])
        df_top3 = rootdata_deal(df,df_reason['维度'].iloc[2],df_reason['条件'].iloc[2])
        x_data = list(df_kpi['day'])
        y_data = list(df_kpi['ka_rate'])
        y_data1 = df_top1['%s_ka_rate'%df_reason['维度'].iloc[0]]
        y_data2 = df_top2['%s_ka_rate'%df_reason['维度'].iloc[1]]
        y_data3 = df_top3['%s_ka_rate'%df_reason['维度'].iloc[2]]
        
        line2 = Line(init_opts=opts.InitOpts(theme='light',bg_color=JsCode(bg_color_js),width='700px',height='350px'))
        line2.add_xaxis(x_data)
        line2.add_yaxis('卡顿率',y_data)
        line2.add_yaxis('去除"%s=%s"数据后的卡顿率'%(df_reason['维度'].iloc[0],df_reason['条件'].iloc[0]),y_data1)
        line2.add_yaxis('去除"%s=%s"数据后的卡顿率'%(df_reason['维度'].iloc[1],df_reason['条件'].iloc[1]),y_data2)
        line2.add_yaxis('去除"%s=%s"数据后的卡顿率'%(df_reason['维度'].iloc[2],df_reason['条件'].iloc[2]),y_data3)
        line2.set_series_opts(label_opts=opts.LabelOpts(is_show=False))
        line2.set_global_opts(legend_opts=opts.LegendOpts(pos_bottom='80%',pos_left='10%'),title_opts=opts.TitleOpts(title="近20天卡顿率根因定位趋势图"))
        make_snapshot(snapshot,line2.render(),"6.png")
        
        num = 6
        picture_html = MIMEText('<br/><html><body><img src="cid:image%s"></body></html><br/>'%num,'html','utf-8')
        msg.attach(picture_html)
        msgImage = MIMEImage(open('%s.png'%num, 'rb').read())
        msgImage.add_header('Content-ID','image%s'%num)
        msg.attach(msgImage)
    else:
        pass
    return msg

# 邮件发送
def mail_send(msg):
    '''
    目的：发送邮件
    msg：msg_make函数的输出
    '''
    
    mail_host = "smtp.qq.com"
    mail_pass = "utroxricwznwbehj" 
    
    s = smtplib.SMTP()
    s.connect(mail_host)
    s.login(mail_sender,mail_pass)
    s.sendmail(mail_sender,to_list,msg.as_string())
    print('发送成功')
    
if __name__ == "__main__":

    # 全局变量
    bg_color_js = """
    new echarts.graphic.RadialGradient(0.3, 0.3, 0.8, [{
            offset: 0,
            color: '#f7f8fa'
        }, {
            offset: 1,
            color: '#cdd0d5'
        }])"""

    to_list =["593107351@qq.com"]
    ccto_list = ["593107351@qq.com"]
    mail_sender = "593107351@qq.com"
    day = '2021-02-23'
    
    # 真实工作中时间是动态的话，一般是每天早上9点利用计划任务管理器调度执行该程序。
    # day = (datetime.datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d')

    # 执行
    df = mysql_datagain(day)
    # 生成文字
    text = analyse_textmake(df,day)
    # 生成图片并保存至本地
    analyse_picturemake(df,day)
    # 生成邮件msg
    msg = msg_make(df,day,text)
    # 发送邮件
    mail_send(msg)
