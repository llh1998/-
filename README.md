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
通过Pymysql连接MYSQL数据库，设置day变量实现动态取数

##  五、数据指标体系构建
采用OSM模型 + 维度建模法的组合来确定数据指标体系的构建。首先明确 Objective：降低全局卡顿，保障用户不流失。其次定义 KPI：以 ka_people / all_people 为核心指标。最后是纵向分层：L1 (管理层)：全站卡顿人数、卡顿率。L2 (运营层)：各 CDN 表现、各平台表现。L3 (执行层)：具体的 roomid 质量、具体的 province + isp 网络节点质量。
	举例说明，首先是构建每日总体的卡顿率，其次是观测每日各维度卡顿率变化，最后是可以构建CDN和roomid的组合维度来搭建bi看板以此来监控每日卡顿数据的变化

##  六、神经网络Prophet时序异常检测算法
由于大多类似卡顿率等核心指标均周期性，传统的异常检测算法难以学习周期性，所以我们选择FaceBook开源的时序异常检测算法神经网络Prophet。

##  七、基于影响度的根因定位算法
其核心借鉴随机森林的特征重要性计算思想。
在随机森林中某个特征X的重要性的计算方法如下：
1：对于随机森林中的每一颗决策树,使用相应的OOB(袋外数据)数据来计算它的袋外数据误差,记为errOOB1。
2：随机地对袋外数据OOB所有样本的特征X加入噪声干扰(相当于删除该列。),再次计算它的袋外数据误差,记为errOOB2。
3：假设随机森林中有Ntree棵树,那么对于特征X的重要性=∑(errOOB2-errOOB1)/Ntree,袋外的准确率大幅度变化,则说明这个特征对于样本的分类结果影响很大,也就是说它的重要程度比较高。
yxd = 去掉之前的卡顿率 - 去掉某维度的卡顿率，yxd越大说明该维度越容易让指标突增，yxd越小说明该维度越容易让指标突降，yxd接近于0，说明该维度完全不影响指标
当Prophet时序异常检测算法识别出存在异常时，程序会运行根因定位算法智能分析出可能的TOP3根因，并绘制影响度表格给予各根因对异常的影响度，以及根因验证图表。

##  八、使用STMP+EMAIL库实现自动化邮件发送

##  九、动态仪表盘制作
光使用python进行管理还是远远不够的，所以通过上文构造的数据指标体系构造动态仪表盘很有必要。效果如下图所示
<img width="1413" height="978" alt="Screenshot 2026-04-05 220619" src="https://github.com/user-attachments/assets/06ba822d-d314-4b8f-9049-39a4a4dc1a63" />
<img width="1409" height="792" alt="image" src="https://github.com/user-attachments/assets/b0f4c184-a53b-4b8b-8618-186675c2ce23" />

##  十、效果
通过每日取数判断是否异常，同时分是否异常决定发送异常时的报表和非异常的报表。实现了自动化数据分析
<img width="1641" height="862" alt="image" src="https://github.com/user-attachments/assets/c1d5f809-497b-4221-ad2a-cd9946598ce6" />
<img width="1427" height="858" alt="image" src="https://github.com/user-attachments/assets/65f0dc44-4214-45a4-b7b7-4fe329975af7" />












































