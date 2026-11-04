# 中国制造业人工智能工作负荷与有效AI服务量：自下而上参数调研

**日期：2026-08-10**

## 摘要

目前没有足够直接文献支持给中国制造业设一个统一的“AI服务强度增长系数”。现有证据真正能约束的是不同层次的变量，而且这些变量的证据质量差异很大。更稳妥的结构是：

\[
Q_{j,t}
=
E_{j,t}
\cdot A_{j,t}
\cdot W_{j,t}
\cdot T_{j,t}
\cdot C_{j,t}
\cdot S_{j,t}
\]

其中：

- \(E\)：潜在业务事件/任务数量；
- \(A\)：企业或任务的AI生产性采用率；
- \(W\)：采用企业内部符合条件工作流的AI覆盖率；
- \(T\)：每个业务事件形成的AI任务数；
- \(C\)：每个AI任务实际触发的基础模型调用数；
- \(S\)：每次模型调用的计算规模。

硬件效率、量化、speculative decoding、GPU性能、PUE等应放在下一层“服务量→电力”转换中，不能再次混入 \(Q\)。

---

## 1. IBM“3%→25%”到底是什么

这条数字可以用，但要非常谨慎。

IBM在2025年6月10日发布的 *From AI projects to profits* 相关材料明确说，调查覆盖**全球2,900名高管**，受访者预计 **AI-enabled workflows 从“当前3%”提高到2025年底25%**。

来源：  
https://newsroom.ibm.com/2025-06-10-IBM-Study-Businesses-View-AI-Agents-as-Essential%2C-Not-Just-Experimental

但IBM后来另一篇官方页面把同一项2,900人研究写成：

> AI-enabled workflows 从**2024年的3%**上升至**2026年的25%**。

来源：  
https://www.ibm.com/think/topics/aws-cloud-adoption-framework

因此这里有两个问题：

1. **不是400人调查，而是2,900名全球高管。**
2. IBM不同官方页面对3%和25%的时间标签并不一致：一个写“today→end-2025”，另一个写“2024→2026”。

更重要的是，没有在公开版本中找到原始调查问卷的完整措辞、workflow分母清单，或制造业单独切片。因此不能把它解释成“采用AI的制造企业内部25%的工作流已经AI化”。

建议将它定义成：

\[
\boxed{\text{aggregate AI-enabled workflow penetration}}
\]

即一个**总体工作流渗透指标**。如果模型已经显式拆成：

\[
A\times W
\]

那么IBM的3%和25%更适合用来**交叉校验 \(A\times W\) 的乘积**，而不是独立指定 \(W\)。

例如：

\[
A_{2030}=0.5,\qquad W_{2030}=0.4
\]

则总体AI工作流渗透率：

\[
A\times W=20\%
\]

与IBM给出的25%预期属于相近量级。

反过来，如果先把IBM的25%设成 \(W\)，再乘一个50%的企业采用率，就得到12.5%；如果又把25/3=8.3倍乘到服务量增长上，就出现重复计算。

**所以IBM的3%→25%只能约束“采用率×条件工作流覆盖率”的联合结果，不能约束prompt、模型调用、token或用电量。**

---

## 2. 表1：主要证据清单

| 任务 | 参数 | 数值 | 单位 | 数据年份 | 地区/行业 | 样本或案例 | 证据类型 | 原始来源 | 页码/图表/位置 | 等级 |
|---|---|---:|---|---|---|---|---|---|---|:---:|
| 跨任务 | 中国制造企业AI采用 | >30% | 规上制造企业 | 2025 | 中国制造业 | 全国规上制造业 | 政府披露 | https://www.digitalchina.gov.cn/2026/xwzx/szkx/202604/t20260421_5311555.htm | 正文“2025年…普及率已超30%” | A- |
| 跨任务 | GenAI生产部署 | 24% | 企业 | 2024调查 | 美国大型制造企业 | 600名制造业高管 | 调查 | https://www.deloitte.com/us/en/insights/industry/manufacturing/2025-smart-manufacturing-survey.html | Technology adoption段 | A- |
| 跨任务 | GenAI试点 | 38% | 企业 | 2024调查 | 美国大型制造企业 | 同上600人 | 调查 | https://www.deloitte.com/us/en/insights/industry/manufacturing/2025-smart-manufacturing-survey.html | 同上 | A- |
| 工作流Agent | AI-enabled workflow | 3%→25% | 全部workflow份额 | 2025发布 | 全球跨行业 | 2,900名高管 | 当前值+预期 | https://newsroom.ibm.com/2025-06-10-IBM-Study-Businesses-View-AI-Agents-as-Essential%2C-Not-Just-Experimental | 新闻稿正文 | B- |
| 办公知识 | 企业Copilot实际采用 | 70% | workforce | 2025 | 法国保险 | Generali France | 企业实际案例 | https://www.microsoft.com/en/customers/story/25382-generali-microsoft-365-copilot | Customer story正文 | B |
| 办公知识 | 使用强度 | 15 | prompts/user/week | 2025 | 同上 | 3,700名M365 Copilot用户 | 企业遥测披露 | https://www.microsoft.com/en/customers/story/25382-generali-microsoft-365-copilot | 同上 | B |
| 业务Agent | 客户订单事件 | 数千 | orders/day | 2025 | 全球消费品制造 | Danone | 企业案例 | https://www.microsoft.com/en/customers/story/25506-danone-microsoft-365-copilot | customer-order段 | B |
| Agent | Production agent轨迹长度 | ~20 | tool turns/trace | 2026 | 跨行业Agent | 100+ production traces | 真实生产trace | https://www.appliedcompute.com/research/inference-benchmark | workload profile | B+ |
| Agent | Office agent轨迹长度 | ~41 | turns/trace | 2026 | 办公Agent | production traces | 真实生产trace | https://www.appliedcompute.com/research/inference-benchmark | office workload | B+ |
| Agent | Agent token形态 | ~10k输入；200–300输出/turn | tokens | 2026 | production agents | 同上 | 真实trace | https://www.appliedcompute.com/research/inference-benchmark | workload distribution | B+ |
| Agent | Agent token放大 | 5–30× | tokens/task vs chatbot | 2026预测 | 全球企业 | Gartner分析 | 研究机构预测 | https://www.gartner.com/en/newsroom/press-releases/2026-03-25-gartner-predicts-that-by-2030-performing-inference-on-an-llm-with-1-trillion-parameters-will-cost-genai-providers-over-90-percent-less-than-in-2025 | inference-cost discussion | B |
| Agent代理 | LLM步骤/工具调用 | 350k / 430k | steps/tool calls | 2026 | 软件开发 | 约4,300真实sessions | 学术真实trace | https://arxiv.org/abs/2606.30560 | 摘要 | A- |
| 排程优化 | 生产排程频率特征 | 日常→连续 | qualitative | 2026 | 饮料制造 | 大型饮料企业 | 生产案例 | https://www.microsoft.com/en/customers/story/26648-sight-machine-microsoft-foundry | scheduling段 | B |
| 排程优化 | 排程收益 | 非增值生产时间-75%，产能+>5% | outcome | 2026 | 饮料制造 | 同上 | 生产案例 | https://www.microsoft.com/en/customers/story/26648-sight-machine-microsoft-foundry | customer story | B |
| 跨任务 | Agent采用 | 25%→50% | GenAI企业中的Agent部署 | 2025→2027预测 | 全球 | Deloitte预测 | 预测 | https://www.deloitte.com/global/en/about/press-room/deloitte-globals-2025-predictions-report.html | 2025 Predictions | B |
| 外部校准 | 全球数据中心电量 | ~945 TWh | TWh/year | 2030 | 全球 | IEA模型 | 能源预测 | https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai | Energy demand from AI | A |
| 外部校准 | 美国数据中心电量 | 176→325–580 | TWh/year | 2023→2028 | 美国 | LBNL/DOE | 能源预测 | https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers | 报告摘要 | A |

中国公开的“AI技术应用普及率超过30%”覆盖的是**广义AI技术**，并不等于30%的企业已经在生产环境大规模使用LLM/Agent/VLM。因此它比较适合做2030 adoption上限/方向性锚点，而不能直接赋给七类生成式AI任务。

---

## 3. “采用率”建议严格定义为生产采用

建议：

\[
A_j=
\frac{\text{已经定期在生产环境使用任务 }j\text{ 的企业}}
{\text{具备该任务潜力的企业}}
\]

而不是：

- 听说过AI；
- 有Copilot账号；
- 做过PoC；
- 正在试点；
- 计划部署。

Deloitte的数据很好地说明为什么必须这么做：制造企业中**24%已经在facility/network层级部署GenAI，但38%仍处于pilot阶段**。把两者加成62%“采用率”会严重高估当前有效推理负荷。

---

## 4. 表2：建议参数范围

下面是目前最适合作为2024/2025→2030情景的参数集。

其中：

- A/B级数字有较强外部证据；
- C/D级数字是证据锚定的研究情景，不应写成预测值；
- 当前值代表约2024–2026的生产使用；
- 2030值是情景，而不是点预测。

### 4.1 办公知识服务

| 参数 | 当前低 | 当前Base | 当前高 | 2030低 | 2030 Base | 2030高 | 推荐依据 | 重复风险 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 企业生产采用率 \(A\) | 0.10 | **0.20** | 0.35 | 0.45 | **0.70** | 0.85 | Generali 70%是成熟知识企业上限代理；制造业整体应更低 | 与W分开 |
| 条件工作流覆盖 \(W\) | 0.15 | **0.30** | 0.50 | 0.45 | **0.65** | 0.80 | 缺制造业实测；用IBM总体workflow渗透交叉校验 | **高** |
| 潜在知识任务/人/日 \(E\) | 5 | **8** | 12 | 5 | **8.4** | 13 | 无直接证据；只给业务活动情景，不用prompt替代 | 低 |
| AI任务/覆盖事件 \(T\) | 1.0 | **1.0** | 1.2 | 1.0 | **1.2** | 1.5 | 修订、检索、生成可能逐渐拆为多个AI任务 | 中 |
| 模型调用/AI任务 \(C\) | 1.0 | **1.2** | 2 | 1.3 | **2.0** | 3 | RAG/验证逐步agent化；复杂Agent不应套在所有办公任务 | 中 |
| 单调用计算规模 \(S\) | 0.7 | **1.0** | 1.5 | 1.1 | **1.5** | 2.5 | Base归一化为当前简单RAG；未来上下文可能增长 | 与效率重复风险高 |

Generali实际观察到15 prompts/user/week，即约3个工作日prompt；这可以约束**实际已发生调用**，但不能直接当潜在工作任务数 \(E\)，因为很多符合条件的任务还没有使用AI。

### 4.2 ERP/MES/QMS/供应链等业务Agent

| 参数 | 当前低 | 当前Base | 当前高 | 2030低 | 2030 Base | 2030高 | 推荐依据 | 重复风险 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| \(A\) | 0.03 | **0.10** | 0.20 | 0.30 | **0.50** | 0.70 | GenAI已部署24%、Agent仍更早期；2030基准低于成熟GenAI总采用 | — |
| \(W\) | 0.05 | **0.20** | 0.30 | 0.25 | **0.40** | 0.65 | 与IBM aggregate workflow penetration联合校验 | **很高** |
| 业务事件/厂/日 \(E\) | 300 | **1000** | 3000 | 330 | **1100** | 3900 | 未找到普通制造厂全系统日志；Danone单订单流已达数千/day | 不应随AI普及增长 |
| \(T\) | 1 | **1** | 1.5 | 1.1 | **1.5** | 2 | 一个业务事件未来可能同时触发分类、核验、决策等 | 中 |
| \(C\) | 1.5 | **2** | 5 | 3 | **8** | 20 | production Agent约20 turns提供高端锚点 | 高 |
| \(S\) | 0.8 | **1** | 2 | 1.2 | **2.5** | 5 | Agent上下文/工具返回显著增加输入tokens | 与C相关 |

未来需求增长的主体应主要来自：

\[
A,\ W,\ C
\]

而不是假定ERP订单数本身增长十倍。

---

## 5. 机器视觉与中央VLM复核

已明确排除普通固定算法视觉，则：

\[
E
\]

不应该是所有camera frames，也不应该是所有产品件数，而应该定义成：

> **经过边缘CV筛选后，符合中央VLM复核条件的潜在异常/疑难事件数。**

目前没有找到可靠公开数据告诉我们“中国制造产线有多少百分比普通视觉结果升级给VLM”。

因此这项必须标记：

> **未找到直接证据。**

建议：

| 参数 | 当前低 | Base | 高 | 2030低 | Base | 高 |
|---|---:|---:|---:|---:|---:|---:|
| VLM生产采用 \(A\) | .01 | **.03** | .08 | .15 | **.35** | .60 |
| 条件视觉工作流覆盖 \(W\) | .02 | **.10** | .20 | .15 | **.30** | .60 |
| 疑难事件/产线/day \(E\) | 5 | **20** | 100 | 6 | **24** | 150 |
| AI tasks/event \(T\) | 1 | **1** | 1.2 | 1 | **1.2** | 2 |
| VLM calls/task \(C\) | 1 | **1** | 2 | 1 | **1.5** | 3 |
| compute/call \(S\) | 1 | **1** | 2 | 1.5 | **2** | 4 |

单调用不建议直接换token，而应该保留：

\[
\{\text{images},\ resolution,\ text\ tokens,\ model\}
\]

例如Base可以定义为：

- 1–4张图片；
- 中等分辨率；
- 数百至数千text input tokens；
- 3B–7B VLM主流；
- 72B/VLM作为高质量敏感性。

**不要同时使用“异常升级率”和“VLM workflow覆盖率”描述同一个筛选过程，否则会重复乘。**

---

## 6. 预测维护与设备诊断

这里最合理的 \(E\) 不是原始传感器点，而是：

> **边缘侧/传统异常检测产生的“有效诊断事件”。**

因此：

\[
raw\ sensor
\rightarrow edge\ filter
\rightarrow effective\ alert
\rightarrow AI
\]

建议参数：

| 参数 | 当前低 | Base | 高 | 2030低 | Base | 高 |
|---|---:|---:|---:|---:|---:|---:|
| \(A\) | .05 | **.15** | .30 | .30 | **.55** | .80 |
| \(W\) | .05 | **.20** | .35 | .30 | **.50** | .75 |
| 有效诊断事件/设备/day | .02 | **.05** | .20 | .03 | **.06** | .30 |
| \(T\) | 1 | **1** | 1.5 | 1 | **1.25** | 2 |
| \(C\) | 1.5 | **2** | 5 | 3 | **8** | 20 |
| \(S\) | .8 | **1** | 2 | 1.2 | **2** | 5 |

Agent未来会查询：

- 设备状态；
- SCADA/MES日志；
- 历史维修记录；
- SOP；
- 配件；
- 工单系统。

因此这类任务比简单RAG更适合使用多步Agent。Applied Compute的20-turn production traces可作为复杂任务上限附近的代理，但不是制造维护的直接测量。

---

## 7. 生产排程和工艺优化

这里应该把两个维度拆开：

\[
\text{触发排程次数}
\]

和

\[
\text{每次触发评估多少候选方案}
\]

Sight Machine/Microsoft的真实饮料制造案例显示，传统排程被描述为日常“damage control”，新系统已经在向**跨班次持续后台优化**演化。

建议：

| 参数 | 当前低 | Base | 高 | 2030低 | Base | 高 |
|---|---:|---:|---:|---:|---:|---:|
| 企业采用 \(A\) | .03 | **.10** | .20 | .25 | **.50** | .75 |
| 工作流覆盖 \(W\) | .05 | **.15** | .30 | .25 | **.45** | .70 |
| 重排/优化事件/厂/day | 1 | **3** | 8 | 1.5 | **4** | 20 |
| 候选AI任务/event \(T\) | 2 | **5** | 20 | 8 | **20** | 100 |
| model calls/task \(C\) | 1 | **1.5** | 3 | 1.5 | **3** | 8 |
| \(S\) | .7 | **1** | 2 | 1.2 | **2** | 4 |

还要注意：

> LLM调用和数学优化器计算不是一种计算。

例如Agent可能：

1. 用LLM构造约束；
2. 调MIP solver；
3. 阅读结果；
4. 修改约束；
5. 再求解。

如果目标是总数据中心/厂内算力电耗，solver CPU/GPU hours应该另列，而不是统统换成LLM token。

---

## 8. 研发仿真、生成式设计和数字孪生

这一类是目前证据最弱、但潜在算力最大的类别之一。

建议：

| 参数 | 当前低 | Base | 高 | 2030低 | Base | 高 |
|---|---:|---:|---:|---:|---:|---:|
| \(A\) | .05 | **.12** | .25 | .25 | **.55** | .80 |
| \(W\) | .05 | **.20** | .35 | .20 | **.45** | .70 |
| design studies/team/day | .2 | **1** | 5 | .3 | **1.5** | 15 |
| simulation/evaluations/study | 5 | **20** | 100 | 30 | **100** | 1000 |
| model calls/evaluation | 1 | **1** | 2 | 1 | **1.5** | 3 |
| compute/evaluation | .5 | **1** | 10 | 1 | **2.5** | 50 |

这里的 \(S\) 最好不要用token，而用：

\[
GPU\text{-}s,\ GPU\text{-}h,\ CPU\text{-}h
\]

或标准化simulation FLOPs。

**这组当前/2030数字目前主要是D级情景参数。** 缺少公开的制造研发平台真实“仿真次数/工程师/day”日志，因此高值绝不能被描述成预测。

---

## 9. 离线RAG建库、embedding和微调

这类任务不适合强行使用统一的：

\[
tasks\times calls/task\times tokens/call
\]

因为三个子任务的自然单位不同。

### Embedding

\[
\text{documents or tokens ingested}
\]

### 文档抽取/清洗

\[
\text{documents}\times LLM\ calls/document
\]

### Fine-tuning

\[
training\ tokens\times epochs
\]

或：

\[
GPU\ hours
\]

所以推荐直接拆成三个offline workload。

2030情景可用：

| 参数 | 当前Base | 2030 Base | 状态 |
|---|---:|---:|---|
| 有RAG/KB企业比例 | 0.15 | **0.60** | C |
| 自动更新覆盖率 | 0.30 | **0.70** | C |
| KB更新频率 | 每周5次 | **每天约2次/等效** | D |
| embedding数据量 | 按新增文档tokens | 按新增文档tokens | 应从数据量推导 |
| LoRA/QLoRA | 季度/半年敏感性 | 月度–季度敏感性 | D |
| full fine-tune | 非Base | 非Base | 不进入主服务量 |

离线任务的最大价值是可调度性：

\[
\sum_{t\in window}Q_t^{offline}\ge Q^{required}
\]

而不是它平均每天占多少固定GPU。

---

## 10. 单次调用的计算规模：最容易与效率重复计算

建议定义一个**逻辑计算规模指标**：

\[
S=
f(
N_{\rm input\ tokens},
N_{\rm output\ tokens},
N_{\rm images},
resolution,
model\ class
)
\]

而不要在这一层加入：

- INT4比BF16快多少；
- L20比A10快多少；
- speculative decoding提升多少；
- GPU generation efficiency。

Agent production trace已经显示，一个成熟Agent调用可能从约10k输入上下文开始，而单步输出通常只是200–300 tokens，因此未来Agent服务的增长可能非常**input-heavy**。

推荐Base分类：

| 调用类别 | Input | Output | 其他 |
|---|---:|---:|---|
| 简单Copilot | 1–2k | 200–400 | — |
| RAG | 2–5k | 200–500 | retrieved context |
| 普通Agent step | **5–10k** | 200–400 | tools/cache |
| 长Agent | 10–50k+ | 200–800 | growing context |
| VLM review | 1–4 images + text | 200–500 | image encoder |
| Digital twin | 不建议token化 | — | GPU/CPU seconds |

然后下一层再定义：

\[
Electricity
=
\frac{Q_{\rm logical\ compute}}
{\eta_{\rm model,software,hardware}}
\times PUE.
\]

这样未来模型量化、蒸馏、缓存、推测解码、GPU换代产生的效率提高只出现一次。

---

## 11. 表3：当前→2030综合有效服务量增长分解

下面的Base倍数是按照前面的**联合情景**机械计算，不是外部预测。

| 任务 | 采用率增长 | 工作流覆盖增长 | 事件频率增长 | 每事件AI任务增长 | 每任务调用数增长 | 单次计算规模增长 | 综合有效服务量增长 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 办公知识 | 3.50 | 2.17 | 1.05 | 1.20 | 1.67 | 1.50 | **≈24×** |
| 业务Agent | 5.00 | 2.00 | 1.10 | 1.50 | 4.00 | 2.50 | **≈165×** |
| VLM异常复核 | 11.67 | 3.00 | 1.20 | 1.20 | 1.50 | 2.00 | **≈151×** |
| 预测维护 | 3.67 | 2.50 | 1.20 | 1.25 | 4.00 | 2.00 | **≈110×** |
| 排程优化 | 5.00 | 3.00 | 1.33 | 4.00 | 2.00 | 2.00 | **≈319×** |
| R&D仿真 | 4.58 | 2.25 | 1.50 | 5.00 | 1.50 | 2.50 | **≈290×** |
| 离线知识/适配* | 4.00 | 2.33 | 2.00 | 1.50 | 2.00 | 1.50 | **≈84×*** |

\* 离线类别的84×仅用于概念比较，**不建议直接入最终模型**，因为embedding、文档解析和微调的计算单位不同。

---

## 12. 为什么几十倍、几百倍增长不荒谬，但也不能直接当预测

以业务Agent为例，165×来自：

\[
5\times2\times1.1\times1.5\times4\times2.5
=165.
\]

这里真正主导的是：

- 更多企业进入生产采用；
- 更多流程接AI；
- 一次业务事件从单步分类变为多步Agent；
- 每步读取更长上下文。

而不是说：

> 中国制造业订单量增长165倍。

Agent token消耗比chatbot高5–30倍的行业预测和生产trace中20–41 turn/trace的事实都支持“**每个有效业务任务的模型活动量显著上升**”这一方向。

但是这些参数**高度相关**。

例如：

- AI workflow覆盖越高，新增的往往是更简单任务，因此平均calls/task可能下降；
- Agent更复杂时，单次调用context更长，但更强模型可能减少反思/重试；
- 自动排程频率增加，单次排程的候选数可能下降；
- VLM普及会使更多普通样本直接被小模型处理，而非全部升级大模型。

所以不能把所有High边界独立相乘。那会轻易得到几千到几万倍、但没有实际意义。

机械乘积必须进一步进行相关性收缩。当前进入模型的**联合情景**为：

| 任务 | 2030 Low综合 | 2030 Base | 2030 High联合情景 |
|---|---:|---:|---:|
| 办公知识 | 12× | **20×** | 40× |
| 业务Agent | 75× | **130×** | 260× |
| VLM异常复核 | 70× | **120×** | 240× |
| 预测维护 | 52× | **90×** | 180× |
| 排程优化 | 145× | **250×** | 500× |
| R&D仿真 | 128× | **220×** | 440× |
| 离线知识/适配 | **分项计算** | **分项计算** | **分项计算** |

这里Base和Low/High都是**模型情景输入**，不是文献点预测。它们保留机械分解得到的任务间相对强弱，但对同时上升的覆盖率、调用数和上下文规模作联合收缩；再使用8/14/28 TWh作为软边界检查。完整小时模型得到7.935/13.658/27.317 TWh/年，而不是精确强制等于外部数值。

---

## 13. 最关键的防重复计算规则

### 规则1：采用率只回答“谁开始使用”

\[
A=
P(\text{enterprise/task adopts AI})
\]

不要把使用深度放进A。

### 规则2：工作流覆盖只回答“采用者内部覆盖多少”

\[
W=
P(\text{workflow AI-enabled}\mid adoption)
\]

如果外部报告提供的是全体企业总体workflow share，则：

\[
P(\text{AI-enabled workflow})=A\times W.
\]

IBM就是这种更适合用来约束乘积的指标。

### 规则3：业务事件量必须先于AI存在

例如订单、设备故障、质量异常：

\[
E
\]

原则上是企业真实业务活动。

“因为用了Agent所以调用更多模型”应该进入 \(T\) 或 \(C\)，而不是再提高E。

### 规则4：机器自动采集增加应进入事件定义，而非采用率

例如更多传感器上线使可分析设备事件增长，这是：

\[
E\uparrow
\]

不是：

\[
A\uparrow.
\]

### 规则5：Agent深度只进调用数

Agent 20 turns：

\[
C\uparrow
\]

不要同时把20倍放进AI task/event。

### 规则6：长context进 \(S\)，不是 \(C\)

同一次模型调用从2k变10k输入：

\[
S\uparrow.
\]

### 规则7：硬件/模型效率不属于服务量

INT4、FP8、新GPU、speculative decoding：

\[
\eta\uparrow
\]

应降低：

\[
kWh/service
\]

而不是降低“有效AI服务需求”。

---

## 14. IBM的3%→25%到底可以约束什么

### 可以约束

\[
\boxed{A\times W}
\]

即企业总体符合条件工作流的AI渗透程度。

它也可以作为业务Agent类2030情景的一个**外部上/中值锚点**。

### 不能约束

它不能直接决定：

- 企业采用率 \(A\)；
- adopter内部条件覆盖率 \(W\)；
- prompt/user；
- events/day；
- tasks/event；
- model calls/task；
- token/call；
- GPU hours；
- electricity。

更不能用：

\[
25/3=8.33
\]

直接说：

> 2026 AI用电是2024年的8.33倍。

IBM的时间标签还存在官方页面之间的不一致，因此不建议把8.33作为严格时间增长率。

---

## 15. 哪些参数目前证据最可靠

### A级/接近A级

- 中国规上制造企业广义AI采用率 >30%；
- Deloitte制造企业GenAI deployed vs pilot区分；
- 企业真实Copilot prompts/user/week；
- Agent production trace中的turn数和context结构；
- 全球/美国数据中心电量预测。

### B/C级

- AI-enabled workflow penetration；
- 制造业task-level adoption；
- Agent调用次数向制造业迁移；
- 单任务典型token长度。

### C/D级、目前最缺

- 普通中国工厂的MES/QMS/CMMS events/day；
- 机器有效报警/设备/day；
- CV→VLM真实升级率；
- 重排次数/factory/day；
- 工业Agent真实calls/task；
- 制造研发simulations/team/day；
- 企业RAG实际token更新量。

---

## 16. 最值得进一步寻找企业日志的参数

如果只能补5个数据，建议优先级是：

1. **MES/QMS/CMMS/ERP逐小时事件量**
2. **AI实际覆盖这些事件的比例**
3. **Agent trace的model calls/task**
4. **每次调用input/output/cache tokens**
5. **CV异常升级到VLM的比例**

因为最终服务量的弹性：

\[
\frac{\partial\ln Q}{\partial\ln x}=1
\]

对每一个乘法参数理论上都相同，但实际上：

- adoption未来可能3–10×；
- workflow coverage可能2–5×；
- Agent calls可能2–10×；
- event frequency通常只1–2×。

所以最值得研究的是：

\[
A,\ W,\ C
\]

以及VLM/R&D中的 \(T\)。

---

## 17. 如何和数据中心用电预测校准

外部预测只能用于**最后的一致性检查**。

IEA Base Case预计全球数据中心电力从2024年的大约460 TWh增长到2030年约945 TWh，大约翻倍；AI是增长的主要驱动。

来源：  
https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai

美国DOE/LBNL则估计：

\[
176\ TWh\ (2023)
\rightarrow
325-580\ TWh\ (2028),
\]

即约1.8–3.3倍。

来源：  
https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers

这明显小于某些AI服务类别可能得到的几十至数百倍增长，**并不矛盾**，因为：

1. AI workload只占数据中心负荷的一部分；
2. 制造AI只占AI负荷的一部分；
3. 很多AI任务当前基数接近零，所以服务量增长倍数很高；
4. GPU每单位计算效率快速提升；
5. 量化/蒸馏/缓存/推测解码降低单位逻辑服务计算需求；
6. GPU利用率提高；
7. PUE改善。

正确闭环是：

\[
\boxed{
\text{Business activity}
\to
\text{effective AI service}
\to
\text{logical compute}
\to
\text{physical accelerator work}
\to
\text{kWh}
}
\]

然后才比较：

- IEA全球约945–950 TWh/2030；
- DOE/LBNL美国325–580 TWh/2028；
- 中国国内权威算力/数据中心用电预测。

**不要反过来为了让中国制造AI用电“匹配”某个数据中心预测而调高或调低采用率。**

---

## 18. 对当前模型的建议

建议彻底取消一个统一的：

\[
\text{AI service intensity growth factor}
\]

改为针对7类业务分别保留至少：

\[
\boxed{
A_j,\ W_j,\ E_j,\ T_j,\ C_j,\ S_j
}
\]

然后2030情景计算：

\[
G_j=
\frac{A_{2030}}{A_0}
\frac{W_{2030}}{W_0}
\frac{E_{2030}}{E_0}
\frac{T_{2030}}{T_0}
\frac{C_{2030}}{C_0}
\frac{S_{2030}}{S_0}.
\]

第一版进入模型的Base增长量级取：

- **办公Copilot/RAG：20×**
- **业务Agent：130×**
- **中央VLM异常复核：120×**
- **设备诊断：90×**
- **排程/优化：250×**
- **R&D仿真：220×，但不确定性最大**
- **离线RAG/微调：不要给统一倍率，分任务计算**

这些数字的价值不是说“文献预测中国2030就是这个倍数”，而是：

> **它们把增长来源完全显式化了。**

这样当将来拿到更好的企业日志，例如“实际只有0.5%的CMMS告警进入Agent”或“生产Agent平均只有4个LLM calls而不是8个”，可以直接替换那个参数，而不需要推翻整个服务强度假设。

---

## 19. 主要来源

1. IBM, *From AI projects to profits*, 2025  
   https://newsroom.ibm.com/2025-06-10-IBM-Study-Businesses-View-AI-Agents-as-Essential%2C-Not-Just-Experimental

2. Deloitte, *2025 Smart Manufacturing and Operations Survey*  
   https://www.deloitte.com/us/en/insights/industry/manufacturing/2025-smart-manufacturing-survey.html

3. Microsoft, Generali France Copilot customer story  
   https://www.microsoft.com/en/customers/story/25382-generali-microsoft-365-copilot

4. Microsoft, Danone Copilot customer story  
   https://www.microsoft.com/en/customers/story/25506-danone-microsoft-365-copilot

5. Applied Compute, *Benchmarking Inference Engines on Agentic Workloads*  
   https://www.appliedcompute.com/research/inference-benchmark

6. Gartner, 2026 inference economics forecast  
   https://www.gartner.com/en/newsroom/press-releases/2026-03-25-gartner-predicts-that-by-2030-performing-inference-on-an-llm-with-1-trillion-parameters-will-cost-genai-providers-over-90-percent-less-than-in-2025

7. TraceLab / agent production traces  
   https://arxiv.org/abs/2606.30560

8. Microsoft/Sight Machine manufacturing scheduling case  
   https://www.microsoft.com/en/customers/story/26648-sight-machine-microsoft-foundry

9. Deloitte, 2025 Predictions  
   https://www.deloitte.com/global/en/about/press-room/deloitte-globals-2025-predictions-report.html

10. IEA, *Energy and AI*  
    https://www.iea.org/reports/energy-and-ai/energy-demand-from-ai

11. U.S. DOE/LBNL data center electricity report  
    https://www.energy.gov/articles/doe-releases-new-report-evaluating-increase-electricity-demand-data-centers

12. 数字中国/中国制造业AI应用普及率  
    https://www.digitalchina.gov.cn/2026/xwzx/szkx/202604/t20260421_5311555.htm
