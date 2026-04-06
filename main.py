import pymysql
import pandas as pd
import smtplib
import matplotlib.pyplot as plt
import matplotlib
import io
from itertools import combinations
from neuralprophet import NeuralProphet
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import timedelta
# 解决环境绘图兼容性
matplotlib.use('Agg') 
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
def analyze_specific_day(target_date_str):
    # 1. 核心配置 (以下空白未填处为个人信息)
    csv_path = r"C:\Users\21185\Desktop\video_quality_data.csv"
    DB_CONF = {'host': '', 'user': 'root', 'password': '', 'database': '', 'charset': 'utf8mb4'}
    EMAIL_CONF = {
        'smtp_server': 'smtp.qq.com', 
        'sender': '2118504150@qq.com', 
        'password': '', 
        'receiver': '2118504150@qq.com'
    }
    conn = pymysql.connect(**DB_CONF)
    try:
        cursor = conn.cursor()
        #2. 全量数据处理 
        df = pd.read_sql("SELECT * FROM video_quality_data", conn)
        df['day'] = pd.to_datetime(df['day'])
        target_date = pd.to_datetime(target_date_str)
        # 计算每日汇总
        daily = df.groupby('day').agg({'ka_people':'sum', 'all_people':'sum'}).reset_index()
        daily['y'] = daily['ka_people'] / daily['all_people']
        daily_map = daily.set_index('day')['y'].to_dict()
        # 趋势计算
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
        # 异常判定-神经网络prophet模型
        model_df = daily.rename(columns={'day': 'ds'})[['ds', 'y']].dropna()
        m = NeuralProphet(n_lags=3, weekly_seasonality=True)
        m.fit(model_df, freq='D', epochs=50, progress=None)
        forecast = m.predict(model_df[['ds', 'y']])
        day_stat = forecast[forecast['ds'] == target_date]
        yhat = day_stat['yhat1'].values[0]
        threshold = 2 * (forecast['y'] - forecast['yhat1']).std()
        is_anomaly = (current_y - yhat) > threshold
        df_day = df[df['day'] == target_date].copy()
        #  邮件内容构建 
        msg = MIMEMultipart('related')
        
        #  异常分支：
        #核心算法：计算 yxd影响度
        #逻辑：总卡顿率 - (剔除该组后的卡顿率)
        if is_anomaly:
            msg['Subject'] = f"【告警】{target_date_str} 质量异常诊断"
            base_dims = ['user_plat', 'cdn_name', 'province', 'isp','roomid']
            rca_list = []
            for r in range(1, 3):
                for dims in combinations(base_dims, r):
                    g = df_day.groupby(list(dims), as_index=False)[['ka_people', 'all_people']].sum()
                    value_all = g['ka_people'].sum()
                    cnt_all = g['all_people'].sum()
                    if cnt_all == 0: continue
                    rate_all = value_all / cnt_all
                    g['yxd'] = g.apply(
                        lambda row: rate_all - (value_all - row['ka_people']) / (cnt_all - row['all_people']) 
                        if (cnt_all - row['all_people']) != 0 else 0, 
                        axis=1
                    )
                    g['rate_del'] = rate_all - g['yxd']
                    g['dimension'] = " + ".join(dims)
                    g['factor'] = g[list(dims)].astype(str).agg(' | '.join, axis=1)
                    rca_list.append(g[(g['yxd'] > 0) & (g['all_people'] > 30)])
            res_df = pd.concat(rca_list).sort_values('yxd', ascending=False).head(5)
            rows = "".join([
                f"<tr>"
                f"<td>{r.dimension}</td>"
                f"<td>{r.factor}</td>"
                f"<td><b>{r.yxd:.4%}</b></td>"
                f"<td>{int(r.ka_people)}</td>"
                f"<td>{int(r.all_people)}</td>"
                f"<td>{(r.ka_people/r.all_people):.2%}</td>"
                f"</tr>" for _, r in res_df.iterrows()
            ])
            detail_content = f"""
            <h3>根因定位详情：</h3>
            <p style="color:gray;">* 影响度：该因子对整体转化率的拉升/拉低绝对值</p>
            <table border='1' cellspacing='0' cellpadding='5' style='border-collapse:collapse; width:100%;'>
                <tr bgcolor='#eee'>
                    <th>诊断维度</th><th>具体异常因子</th><th>影响度</th><th>卡顿人数</th><th>总人数</th><th>该项卡顿率</th>
                </tr>
                {rows}
            </table>"""
            room_html = ""
        else:
            # -非异常分支
            msg['Subject'] = f"【日报】{target_date_str} 业务质量监控大盘"
            end_date = target_date
            start_date = target_date - timedelta(days=6)
            week_df = daily[(daily['day'] >= start_date) & (daily['day'] <= end_date)].sort_values('day')
            x_dates = week_df['day'].dt.strftime('%m-%d')
            fig = plt.figure(figsize=(22, 16), facecolor='white') 
            #图1：趋势双轴图 
            ax1 = plt.subplot(2, 2, 1)
            ax1_2 = ax1.twinx()
            max_people = week_df['all_people'].max()
            ax1.bar(x_dates, week_df['all_people'], color='#FF9E1B', label='总观看人数')
            ax1.set_ylim(0, max_people * 1.35) # 顶部留 35% 空间，防止打架
            ax1.set_ylabel("观看人数", fontsize=15, fontweight='bold')
            ax1_2.set_ylabel("卡顿率 (%)", fontsize=15, fontweight='bold')
            ax1.set_title("全网质量趋势：人数和卡顿率", fontsize=20, fontweight='bold', pad=25)
            ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ',')))
            ax1.tick_params(axis='both', labelsize=14)
            ax1_2.tick_params(axis='y', labelsize=14)
            lines, labels = ax1.get_legend_handles_labels()
            lines2, labels2 = ax1_2.get_legend_handles_labels()
            ax1_2.legend(lines + lines2, labels + labels2, loc='upper right', fontsize=14)
            # 图2：CDN 质量排位
            ax2 = plt.subplot(2, 2, 2)
            cdn_data = df_day.groupby('cdn_name').agg({'ka_people':'sum', 'all_people':'sum'})
            cdn_data['rate'] = (cdn_data['ka_people'] / cdn_data['all_people']) * 100
            cdn_data = cdn_data.sort_values('rate', ascending=False)
            avg_rate = (df_day['ka_people'].sum() / df_day['all_people'].sum()) * 100
            cdn_bars = ax2.bar(cdn_data.index, cdn_data['rate'], color='#FF9E1B')
            ax2.axhline(avg_rate, color='red', linestyle='--', alpha=0.7, label=f'全网平均({avg_rate:.2f}%)')
            ax2.set_title("各 CDN 厂商质量对比 ", fontsize=20, fontweight='bold', pad=25)
            ax2.bar_label(cdn_bars, fmt='%.2f%%', padding=5, fontsize=14, fontweight='bold')
            ax2.set_ylabel("卡顿率 (%)", fontsize=15, fontweight='bold')
            ax2.tick_params(axis='both', labelsize=14)
            ax2.legend(fontsize=14)
            # 图3：风险矩阵 
            ax3 = plt.subplot(2, 2, 3)
            prov_data = df_day.groupby('province').agg({'all_people':'sum', 'ka_people':'sum'})
            prov_data['rate'] = (prov_data['ka_people'] / prov_data['all_people']) * 100
            top_prov = prov_data.sort_values('all_people', ascending=False).head(12) 
            x_units = top_prov['all_people'] / 10000  # 换算成“万人”
            scatter = ax3.scatter(x_units, top_prov['rate'], 
                                 s=x_units * 35, 
                                 alpha=0.6, c=top_prov['rate'], cmap='RdYlGn_r')
            for i, txt in enumerate(top_prov.index):
                ax3.annotate(txt, (x_units.iloc[i], top_prov['rate'].iloc[i]), 
                             xytext=(6, 6), textcoords='offset points', fontsize=14)
            ax3.set_title("重点区域风险矩阵 (右上角为高危)", fontsize=20, fontweight='bold', pad=25)
            ax3.set_xlabel("观看人数 (单位：万人)", fontsize=15, fontweight='bold')
            ax3.set_ylabel("卡顿率 (%)", fontsize=15, fontweight='bold')
            ax3.tick_params(axis='both', labelsize=14)
            ax3.grid(True, linestyle=':', alpha=0.5)
            # 平台构成环形图
            ax4 = plt.subplot(2, 2, 4)
            plat_data = df_day.groupby('user_plat')['all_people'].sum()
            def plat_label(pct, all_vals):
                absolute = int(round(pct/100.*sum(all_vals)))
                abs_str = f"{absolute/10000:.1f}万" if absolute >= 10000 else str(absolute)
                return f"{pct:.1f}%\n({abs_str})"
            wedges, texts, autotexts = ax4.pie(plat_data, labels=plat_data.index, 
                    autopct=lambda pct: plat_label(pct, plat_data),
                    startangle=90, pctdistance=0.8, colors=plt.cm.Pastel2.colors)
            plt.setp(texts, size=15) 
            plt.setp(autotexts, size=14, fontweight="bold") 
            centre_circle = plt.Circle((0,0), 0.60, fc='white')
            fig.gca().add_artist(centre_circle)
            ax4.set_title("用户终端平台分布", fontsize=20, fontweight='bold', pad=25)
            plt.subplots_adjust(wspace=0.45, hspace=0.5) 
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=200, bbox_inches='tight') 
            buf.seek(0)
            msg_img = MIMEImage(buf.read())
            msg_img.add_header('Content-ID', '<visual_report>')
            msg.attach(msg_img)
            detail_content = "<h3>业务多维看板：</h3><img src='cid:visual_report' style='max-width:1200px; width:100%;'>"
            room_agg = df_day.groupby('roomid').agg({'ka_people':'sum', 'all_people':'sum'})
            room_agg['rate'] = room_agg['ka_people'] / room_agg['all_people']
            room_threshold = 0.10
            black_list = room_agg[(room_agg['all_people'] > 1000) & (room_agg['rate'] > room_threshold)].sort_values('rate', ascending=False).head(5)
            if not black_list.empty:
                room_rows = "".join([f"<tr><td>{idx}</td><td>{int(r.ka_people)}</td><td>{int(r.all_people)}</td><td style='color:red;font-weight:bold;'>{r.rate:.2%}</td></tr>" for idx, r in black_list.iterrows()])
                room_html = f"""<div style="margin-top:30px; border-top:2px solid #eee; padding-top:20px;"><h3 style="color:#C0392B;">重点直播间体验黑名单</h3><table border='1' cellspacing='0' cellpadding='8' style='border-collapse:collapse; width:100%; text-align:center;'><tr bgcolor='#FADBD8'><th>房间 ID</th><th>卡顿人数</th><th>总人数</th><th>卡顿率</th></tr>{room_rows}</table></div>"""
            else:
                room_html = "<div style='margin-top:30px; border-top:2px solid #eee; padding-top:20px;'><h3 style='color:#27AE60;'>重点直播间体验看板</h3><p>今日大盘稳健，无核心直播间卡顿异常。</p></div>"
        # 合并正文并发送
        full_html = f"<html><body> {trend_html} {detail_content} {room_html} </body></html>"
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
