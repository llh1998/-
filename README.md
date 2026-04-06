<h1 align="center">数据分析项目（归因分析）</h1>

## 一、背景介绍

用户观看体验是视频公司的生命线，而卡顿是影响用户体验的关键因素。作为数据分析师，我们应对卡顿等核心指标进行数据监控，利用异常检测算法自动发现异常点，并且利用根因定位算法分析其原因，并采取多维度下钻分析及数据可视化的手段形成每日智能监控邮件日报，为公司生命线保驾护航。

## 二、数据介绍

user_plat：用户使用什么平台观看视频，例如adr/ios
roomid：视频id
province：用户所在省份
isp：用户所用运营商
ka_people：当天总卡顿人数
all_people：当天总观看视频人数
cdn_name：CDN的全称是Content Delivery Network，即内容分发网络。CDN的基本原理是广泛采用各种缓存服务器，将这些缓存服务器分布到用户访问相对集中的地区或网络中，在用户访问网站时，利用全局负载技术将用户的访问指向距离最近的工作正常的缓存服务器上，由缓存服务器直接响应用户请求

##  三、流程框架
<img width="951" height="514" alt="image" src="https://github.com/user-attachments/assets/ae89d0b3-0055-46a4-b1b9-9bf9fca49e37" />

 
##  四、python连接mysql取数
通过Pysql连接本地MYSQL数据库，设置target_date变量实现动态取数

##  五、数据指标体系构建
通过osm模型来构造我们的数据指标体系：1. 核心目标通常是提供流畅的视频观看体验，提升用户留存。具体目标是降低播放卡顿率，优化不同地域运营商的连接质量。
2. 业务策略是为了达成上述目标，可以采取以下策略：首先是CDN调度策略，也就是在不同省份和运营商之间，选择质量更优的CDN厂商；其次是平台适配策略，针对不同的用户平台进行性能调优；
最后是监控人数较多的roomid以及它的卡顿率。
3. 为了衡量上述业务策略，可以采取以下指标：(1)总体卡顿率 = sum(ka_people)\sum(all_people)和总观看人数all_people
(2)CDN 质量分布指标是不同cdn_name下的卡顿率对比；区域质量覆盖指标是不同province和isp的卡顿率排名；平台兼容性是不同用户平台的表现差异。
(3)通过第二层维度对时间和roomid进行切片分析
综上就构造好了一个数据指标体系


##  六、神经网络Prophet时序异常检测算法
由于大多类似卡顿率等核心指标均周期性，传统的异常检测算法难以学习周期性，所以我们选择FaceBook开源的时序异常检测算法神经网络Prophet算法。
神经网络prophet算法可以排除掉周期性趋势这两方面的影响，这就是它为什么有效的原因

##  七、根因定位
如果去除某维度某元素的数据时，发现KPI恢复正常，则该维度该元素就是KPI异常的根因。其影响度计算公式为：yxd = value1/cnt1 - ((value1 - value2) / (cnt1 - cnt2))
value1/cnt1 ：比如是2021-02-23日的卡顿率，((value1 - value2) / (cnt1 - cnt2)) ： 2021-02-23日的去掉七牛云数据的卡顿率，yxd = 去掉之前的卡顿率 - 去掉某维度的卡顿率。
yxd越大说明该维度越容易让指标突增，yxd越小说明该维度越容易让指标突降，yxd接近于0，说明该维度完全不影响指标。
同时的话，我们不止考虑某一个特定维度的影响，还会考虑交叉维度是否为异常的根因。

##  八、使用STMP+EMAIL库实现自动化邮件发送
通过自动化邮报，可以让管理层只需打开邮报就知道当天的异常情况。这里用到的stmp+email的python相关库
<img width="1609" height="855" alt="image" src="https://github.com/user-attachments/assets/0873bedc-589b-444f-b4ad-4106eb1f44c8" />
<img width="1606" height="836" alt="image" src="https://github.com/user-attachments/assets/a7226acc-f84c-49c0-88bf-792ce5a0a410" />
<img width="1621" height="813" alt="image" src="https://github.com/user-attachments/assets/61cbfddd-ab21-49a4-8d31-0c193df11986" />


##  九、动态仪表盘制作
通过动态仪表盘能比较形象看到指标的变化
<img width="1413" height="978" alt="Screenshot 2026-04-05 220619" src="https://github.com/user-attachments/assets/06ba822d-d314-4b8f-9049-39a4a4dc1a63" />
<img width="1409" height="792" alt="image" src="https://github.com/user-attachments/assets/b0f4c184-a53b-4b8b-8618-186675c2ce23" />

















































