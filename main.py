import pymysql
import pandas as pd
import smtplib
import matplotlib.pyplot as plt
import io
from itertools import combinations
from neuralprophet import NeuralProphet
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import timedelta
import matplotlib
# 解决环境绘图兼容性
matplotlib.use('Agg') 
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
def analyze_specific_day(target_date_str):
1. 核心配置
    csv_path = r"C:\Users\21185\Desktop\dataanalysis.csv"
    DB_CONF = {'host': '127.0.0.1', 'user': 'root', 'password': '123456', 'database': 'report', 'charset': 'utf8mb4'}
    EMAIL_CONF = {
        'smtp_server': 'smtp.qq.com', 
        'sender': '2118504150@qq.com', 
        'password': 'bfefumqodtawdbjb', 
        'receiver': '2118504150@qq.com'
    }
    
    conn = pymysql.connect(**DB_CONF)
    try:
        cursor = conn.cursor()
        # 数据库初始化 (如果表为空则导入)
        cursor.execute("SELECT COUNT(1) FROM video_quality_data")
        if cursor.fetchone()[0] == 0:
            df_init = pd.read_csv(csv_path)
            cursor.executemany("INSERT INTO video_quality_data VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", df_init.values.tolist())
            conn.commit()
 2. 全量数据处理 
        df = pd.read_sql("SELECT * FROM video_quality_data", conn)
        df['day'] = pd.to_datetime(df['day'])
        target_date = pd.to_datetime(target_date_str)

        daily = df.groupby('day').agg({'ka_people':'sum', 'all_people':'sum'}).reset_index()
        daily['y'] = daily['ka_people'] / daily['all_people']
        daily_map = daily.set_index('day')['y'].to_dict()

        current_y = daily_map.get(target_date, 0)
        prev_day = target_date - timedelta(days=1)
        diff_day = (current_y - daily_map.get(prev_day)) if daily_map.get(prev_day) else None
        last_week_day = target_date - timedelta(days=7)
        diff_week = (current_y - daily_map.get(last_week_day)) if daily_map.get(last_week_day) else None

        def format_diff(diff):
            if diff is None: return "数据缺失"
            color = "#ff0000" if diff > 0 else "#008000"
            symbol = "↑ 上升" if diff > 0 else "↓ 下降"
            return f'<span style="color: {color}; font-weight: bold;">{symbol} {abs(diff):.4%}</span>'

        trend_html = f"""
        <div style="background-color: #f9f9f9; padding: 15px; border-left: 5px solid #2196F3; margin-bottom: 20px;">
            <p style="margin: 5px 0;"><b>今日总体卡顿率：</b> <span style="font-size: 18px;">{current_y:.4%}</span></p>
            <p style="margin: 5px 0;"><b>较昨日环比：</b> {format_diff(diff_day)}</p>
            <p style="margin: 5px 0;"><b>较上周同比：</b> {format_diff(diff_week)}</p>
        </div>
        """
 3. 异常判定 
        model_df = daily.rename(columns={'day': 'ds'})[['ds', 'y']].dropna()
        m = NeuralProphet(n_lags=3, weekly_seasonality=True)
        m.fit(model_df, freq='D', epochs=50, progress=None)
        forecast = m.predict(model_df[['ds', 'y']])
        
        day_stat = forecast[forecast['ds'] == target_date]
        yhat = day_stat['yhat1'].values[0]
        threshold = 2 * (forecast['y'] - forecast['yhat1']).std()
        is_anomaly = (current_y - yhat) > threshold
        df_day = df[df['day'] == target_date].copy()
 4. 邮件内容构建 
        msg = MIMEMultipart('related')
        
        if is_anomaly:
                      异常分支：输出根因表格 
            msg['Subject'] = f"【告警】{target_date_str} 质量异常诊断"
            base_dims = ['user_plat', 'cdn_name', 'province', 'isp']
            rca_list = []
            for r in range(1, 3):
                for dims in combinations(base_dims, r):
                    g = df_day.groupby(list(dims)).agg({'ka_people':'sum', 'all_people':'sum'}).reset_index()
                    v_all, c_all = g['ka_people'].sum(), g['all_people'].sum()
                    g['yxd'] = g.apply(lambda row: (row['ka_people']/row['all_people'] - v_all/c_all) * (row['all_people']/c_all) if c_all!=0 else 0, axis=1)
                    g['dimension'], g['factor'] = " + ".join(dims), g[list(dims)].astype(str).agg(' | '.join, axis=1)
                    rca_list.append(g[(g['yxd'] > 0) & (g['all_people'] > 30)])
            res_df = pd.concat(rca_list).sort_values('yxd', ascending=False).head(3)
            rows = "".join([f"<tr><td>{r.dimension}</td><td>{r.factor}</td><td>{r.yxd:.4f}</td><td>{int(r.ka_people)}</td><td>{int(r.all_people)}</td><td>{(r.ka_people/r.all_people):.2%}</td></tr>" for _, r in res_df.iterrows()])
            detail_content = f"<h3>根因定位详情：</h3><table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse;'> <tr bgcolor='#eee'><th>维度</th><th>因子</th><th>影响度</th><th>卡顿人数</th><th>总人数</th><th>卡顿率</th></tr> {rows} </table>"
        
        else:
           深度优化 非异常分支：日报看板 
            msg['Subject'] = f"【日报】{target_date_str} 业务质量看板"
            
           1. 筛选近一周数据 
            end_date = target_date
            start_date = target_date - timedelta(days=6)
            mask = (daily['day'] >= start_date) & (daily['day'] <= end_date)
            week_df = daily.loc[mask].sort_values('day')
          
            fig = plt.figure(figsize=(16, 20))
            x_dates = week_df['day'].dt.strftime('%m-%d')
            x_indexes = range(len(x_dates))
            width = 0.35 

            图1：近一周总体卡顿率趋势折线图 
            ax1 = plt.subplot(3, 2, 1)
            ax1.plot(x_dates, week_df['y']*100, marker='o', color='#2196F3', linewidth=2, label='卡顿率%')
            ax1.set_title("近一周总体卡顿率趋势 (%)", fontsize=14)
            ax1.set_ylim(0, max(week_df['y']*100) * 1.2) 
            ax1.grid(True, linestyle='--', alpha=0.5)
            ax1.legend()

            图2
            ax2 = plt.subplot(3, 2, 2)
            ax2.bar([i - width/2 for i in x_indexes], week_df['all_people'], width, label='总人数', color='#BBDEFB')
            ax2.bar([i + width/2 for i in x_indexes], week_df['ka_people'], width, label='卡顿人数', color='#F44336')
            ax2.set_xticks(x_indexes)
            ax2.set_xticklabels(x_dates)
            ax2.set_title("近一周人数规模对比", fontsize=14)
           自动调整Y轴刻度，避免科学计数法影响阅读
            ax2.ticklabel_format(style='plain', axis='y') 
            ax2.legend()

           自定义饼图标签函数：同时显示数值和百分比
            def func_pie(pct, allvals):
                absolute = int(round(pct/100.*sum(allvals)))
                return f"{absolute:d}\n({pct:.1f}%)"

          图3：各平台观看人数饼图 
            ax3 = plt.subplot(3, 2, 3)
            plat_data = df_day.groupby('user_plat')['all_people'].sum()
            ax3.pie(plat_data, labels=plat_data.index, autopct=lambda pct: func_pie(pct, plat_data),
                    startangle=140, colors=plt.cm.Pastel1.colors, textprops={'fontsize': 10})
            ax3.set_title("各平台观看人数占比", fontsize=14)

            图4：运营商观看人数饼图
            ax4 = plt.subplot(3, 2, 4)
            isp_data = df_day.groupby('isp')['all_people'].sum()
            ax4.pie(isp_data, labels=isp_data.index, autopct=lambda pct: func_pie(pct, isp_data),
                    startangle=140, colors=plt.cm.Pastel2.colors, textprops={'fontsize': 10})
            ax4.set_title("运营商观看人数占比", fontsize=14)

           图5：各省份观看人数分布
            ax5 = plt.subplot(3, 1, 3)
            prov_data = df_day.groupby('province')['all_people'].sum().sort_values(ascending=True).tail(15)
            bars = ax5.barh(prov_data.index, prov_data.values, color='#4CAF50')
            ax5.set_title("Top 10 省份观看人数分布", fontsize=14)
            ax5.bar_label(bars, padding=3, fmt='%.0f') # 在条形图末端标注数值
            ax5.ticklabel_format(style='plain', axis='x')

            plt.tight_layout(pad=5.0)
            
        保存并关联邮件内容
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=120)
            buf.seek(0)
            msg_img = MIMEImage(buf.read())
            msg_img.add_header('Content-ID', '<visual_report>')
            msg.attach(msg_img)
            detail_content = "<h3>业务多维看板：</h3><img src='cid:visual_report' style='max-width:1000px;'>"

        合并正文并发送
        full_html = f"<html><body> {trend_html} {detail_content} </body></html>"
        msg.attach(MIMEText(full_html, 'html'))
        msg['From'], msg['To'] = EMAIL_CONF['sender'], EMAIL_CONF['receiver']

        with smtplib.SMTP_SSL(EMAIL_CONF['smtp_server'], 465) as server:
            server.login(EMAIL_CONF['sender'], EMAIL_CONF['password'])
            server.sendmail(EMAIL_CONF['sender'], EMAIL_CONF['receiver'], msg.as_string())
        print(f"分析完成：{target_date_str} 邮件已发送。")

    except Exception as e:
        print(f"执行失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_specific_day('2021-02-22')
