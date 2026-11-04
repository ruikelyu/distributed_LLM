# 中国与美国大型商业云数据中心物理参数调研

**研究用途：** 中国制造业 AI 在 `II_1host` 集中自建、中国境内大型云采购、美国境内大型云采购之间的物理资源与环境边界比较  
**调研日期：** 2026-08-11  
**边界：** 仅研究数据中心现场计算、电力、冷却、水、建筑、土地与噪声；**不包含发电侧取水或耗水**。

---

# 1. 执行摘要

## 1.1 能否形成“中国大型云数据中心平均值”？

**没有足够证据形成严格意义上的中国全国代表性平均。**

主要原因：

1. 阿里、腾讯等能够披露自建/自有数据中心组合PUE，但公开页面通常没有同时披露“中国境内IT电量”或“中国境内IT MW”，因此无法按照IT电量或容量构造全国加权平均。
2. 华为云、天翼云、移动云、联通云较容易从政府环评、项目审批和工信部案例得到设施级数据，但通常缺失全国组合IT电量。
3. 水方面披露更薄弱。没有找到中国大型商业云厂商国家级组合的年度现场取水量、WUE和水源结构，可以与其中国IT电量形成一致边界。
4. 冷却塔、干冷器、风冷冷凝器和蒸发冷却等技术有大量项目级证据，但没有公开“按IT MW加权的全国技术份额”。
5. 建筑和土地可以从若干大型项目计算单位IT MW强度，但样本不是随机样本，也不知道覆盖中国大型商业云容量的比例。

因此本报告将中国结果命名为：

> **中国大型云/运营商数据中心“可观测样本情景”**

而不是“中国真实平均”。

PUE是中国证据最强的参数。2024–2025的直接运营数据包括：

- 阿里云自建数据中心2024财年平均PUE：**1.200**；
- 腾讯自有数据中心PUE：2024年约**1.257**，2025年约**1.246**；
- AWS中国组合2024–2025 PUE：**1.25**，可作为补充云运营参照；
- 乌兰察布华为云服务数据中心自然冷却模式月度PUE约**1.22**，但不是全年组合平均。

因此中国大型云可观测样本的PUE建议情景为：

```text
Low  = 1.20
Base = 1.24
High = 1.25
```

该值是**方法D：可观测运营样本情景**，不是容量或IT电量加权的国家平均。

中国国家级WUE、水源份额和最终排热技术份额：**NR**。

---

## 1.2 能否形成“美国大型云数据中心平均值”？

美国的公开程度明显更高，但仍不足以形成完整的IT电量加权全国平均。

最强证据来自：

- AWS：直接公开美国四个Region的年度PUE和**withdrawal WUE**；
- Google：公开大量美国园区的季度和TTM PUE；
- Microsoft：公开Americas组合PUE/WUE，但**Americas不等于美国**；
- California Energy Commission：Microsoft等设施的项目许可中披露关键IT MW、PUE设计值、建筑面积、土地、水源、水量、冷却方式和噪声。

因此美国可以形成：

> **商业云运营样本较强的低—中—高情景**

但不能称为严格的“美国云数据中心全国IT电量加权平均”。

### PUE

2025年AWS美国Region：

- Northern Virginia：1.15
- Ohio：1.12
- Northern California：1.18
- Oregon：1.12

Google 2025年美国园区TTM PUE大量位于约1.04–1.14。

Microsoft FY25 Americas组合PUE为1.16，但包含加拿大及拉美，不能直接作为美国平均，只用于交叉验证。

推荐美国情景：

```text
Low  = 1.09
Base = 1.13
High = 1.18
```

### 现场WUE

AWS定义非常清楚：

```text
WUE = water withdrawn / IT electricity
```

2025年四个美国Region：

- Northern Virginia：0.06 L/kWh-IT
- Ohio：0.06
- Northern California：0.39
- Oregon：0.12

因此推荐美国**withdrawal-WUE**情景：

```text
Low  = 0.06 L/kWh-IT
Base = 0.12 L/kWh-IT
High = 0.39 L/kWh-IT
```

这是AWS美国实际运营Region范围，不是全美国多云加权平均。Microsoft Americas FY25为0.34 L/kWh-IT（其定义为humidification和cooling用水），对高值提供跨厂商合理性校验，但不进入美国国别样本计算。

---

## 1.3 哪些参数目前不能形成国家平均？

中国和美国均无法可靠形成以下全国实际份额：

```text
freshwater_share
reclaimed_water_share
dry_or_air_heat_rejection_share
wet_or_evaporative_heat_rejection_share
existing_capacity_share
expansion_share
greenfield_share
AI/GPU share of IT load
physical GPU utilization
multi-tenant hardware utilization
capacity overbooking ratio
```

全部应记为：

```text
NR
```

而不是为了模型完整性自行填数。

其中建设方式建议使用三个**独立情景**：

1. `existing_capacity_or_retrofit`
2. `existing_campus_expansion`
3. `greenfield_new_build`

目前没有观测权重可以说明这三类在新增云AI需求中的真实比例。

---

# 2. 比较边界

必须同时保留三个边界。

## 2.1 制造企业现场边界

购买公有云GPU后：

```text
manufacturing_site_AI_server_area = 0
manufacturing_site_AI_cooling_water = 0
manufacturing_site_AI_server_noise = 0
```

可以成立。

但这只意味着物理设施从制造企业迁移到云商。

## 2.2 云商设施边界

应计入：

```text
GPU/server IT electricity
network/storage IT electricity
UPS/distribution losses
cooling electricity
onsite cooling water
building floor area
site/land
substation
backup generation
outdoor cooling equipment
noise
```

## 2.3 系统边界

因此禁止：

```text
factory impact = 0
=> system impact = 0
```

正确结构是：

```text
China cloud procurement:
factory incremental facility impact ≈ 0
+
China cloud facility impact

US cloud procurement:
factory incremental facility impact ≈ 0
+
US cloud facility impact
+
cross-border network/data-governance effects if modeled separately
```

---

# 3. 平均值计算方法与本次实际使用方法

## 方法A：IT电量加权

优先公式：

```text
country_average_x =
sum(x_j * IT_energy_j) / sum(IT_energy_j)
```

本轮无法对全部商业云厂商实施，因为厂商国家级IT电量通常NR。

## 方法B：IT容量加权

仅对拥有明确设计IT MW的项目样本可以进行。

例如中国电信芜湖一期：

```text
IT capacity
= 15,620 racks × 6 kW/rack
= 93.72 MW
```

## 方法C：厂商国家组合

AWS提供最接近这一要求的地理组合数据。

Microsoft只到Americas/Asia Pacific等区域，不可直接改称美国或中国。

阿里/腾讯提供公司自建/自有组合PUE，但公开页面未明确给出对应中国境内IT电量权重。

## 方法D：可观测样本与情景

这是本报告多数最终参数采用的方法。

每个参数均明确注明：

```text
aggregation_method
weight_variable
coverage
representativeness_limit
```

---

# 4. 表1：来源登记表

以下代码块可直接复制为CSV。

```csv
source_id,title,publisher,publication_date,access_date,url,source_type,country_scope,company_scope,facility_scope,page_or_table,operating_design_target_or_limit,evidence_grade,exclusion_reason,limitations
S001,AWS Cloud Sustainability,Amazon/AWS,2026-accessed,2026-08-11,https://sustainability.aboutamazon.com/products-services/aws-cloud,official_environmental_data,US+global+China,AWS,AWS regions,PUE/WUE table,operating,A,,China WUE unavailable; no country IT energy weights
S002,Measuring energy and water efficiency for Microsoft datacenters,Microsoft,2026-accessed,2026-08-11,https://datacenters.microsoft.com/sustainability/efficiency/,official_environmental_data,Americas/global,Microsoft,owned-controlled portfolio,FY24-FY25 table,operating,A,,Americas is not identical to US
S003,Power Usage Effectiveness,Google Data Centers,2026-accessed,2026-08-11,https://datacenters.google/efficiency/,official_environmental_data,US+global,Google,facility campuses,2025 quarterly/TTM tables,operating,A,,Facilities support Google services broadly; not Google Cloud-only
S004,Alibaba 2024 ESG Report,Alibaba Group,2024-07-22,2026-08-11,https://www.alibabagroup.com/en-US/document-1752127870676762624,ESG_report,company portfolio,Alibaba Cloud,self-built datacenters,Greener Cloud section,operating,B,,PUE portfolio geography not explicitly separated into China-only IT boundary
S005,Tencent Climate Goals 2025 Metrics,Tencent,2026-06-24,2026-08-11,https://www.tencent.com/en-us/articles/2202371.html,official_environmental_data,company portfolio,Tencent,owned datacenters,climate metrics,operating,B,,Country-specific IT capacity/energy denominator not disclosed
S006,2020国家绿色数据中心经验：乌兰察布华为云服务数据中心,工业和信息化部,2021,2026-08-11,https://www.miit.gov.cn/jgsj/jns/gzdt/art/2021/art_8f143c336a8c4503af31c0eae5861436.html,government_case,China,Huawei Cloud,Wulanchabu facility,cooling/PUE section,operating,B,,Natural-cooling monthly PUE rather than annual fleet PUE
S007,中国电信芜湖大数据中心一期环评审批,芜湖市生态环境局,2023,2026-08-11,https://sthjj.wuhu.gov.cn/hbyw/hjsp/jsxmhpsp/8568779.html,government_EIA,China,China Telecom,Wuhu phase 1,project description,design,A,,Rack power is design capacity; utilization NR
S008,中国联通京津冀数字科技产业园北区项目,天津地方公开报道,2025,2026-08-11,https://www.tjbh.com/c/2025-02-21/1410411.shtml,government_affiliated_news,China,China Unicom,Jing-Jin-Ji north zone,project description,design,B,,Gross floor stated as >100000 m2; exact value NR
S009,阿里巴巴广东云计算数据中心河源改扩建环评公示,河源江东新区,2024,2026-08-11,https://www.hyjdxq.gov.cn/zdlyxxgk/hjbhxxgk/content/post_639054.html,government_EIA,China,Alibaba Cloud,Heyuan campus,project description,design/expansion,A,,IT MW NR
S010,亚马逊中卫数据中心厂房设施建设项目环评批复,中卫市人民政府,2019,2026-08-11,https://www.nxzw.gov.cn/zwgk/bmxxgkml/ssthjj/fdzdgknr_49584/pzjgxx_49610/201911/t20191119_1853761.html,government_EIA,China,AWS China,Zhongwei,noise/cooling equipment,design,A,,Older than preferred period; used only as China facility evidence
S011,San José Data Center 04,California Energy Commission,2023-2026,2026-08-11,https://www.energy.ca.gov/powerplant/backup-generating-system/san-jose-data-center-04,government_environmental_review,US,Microsoft,San Jose SJDC04,project description,design,A,,Project is proposed/under review rather than operating
S012,Microsoft Fourth Revised Project Description SJDC04,Microsoft filing to CEC,2025-07,2026-08-11,https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=101543&tn=264764,regulatory_filing,US,Microsoft,San Jose SJDC04,sections 3.3-3.4,design,A,,Design values are not actual operations
S013,SJDC04 Water Supply Assessment,Microsoft/CEC filing,2022,2026-08-11,https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=80152&tn=245972,water_supply_assessment,US,Microsoft,San Jose SJDC04,section 2,design,A,,Water quantities are design demand
S014,SJDC04 Biological Resources/Noise Evidence,Microsoft/CEC filing,2022,2026-08-11,https://efiling.energy.ca.gov/GetDocument.aspx?DocumentContentId=80139&tn=245947,regulatory_noise_study,US,Microsoft,San Jose SJDC04,section 6.2.10,design_prediction,A,,Boundary prediction rather than operational monitoring
S015,Sustainable by design: next-generation datacenters consume zero water for cooling,Microsoft,2024-12-09,2026-08-11,https://www.microsoft.com/en-us/microsoft-cloud/blog/2024/12/09/sustainable-by-design-next-generation-datacenters-consume-zero-water-for-cooling/,official_technology_disclosure,global+US pilots,Microsoft,new datacenter design,article,design_strategy,A,,Zero cooling-water evaporation does not mean zero total site water
S016,Inside Microsoft's two-decade push to cut water intensity,Microsoft,2026-06-24,2026-08-11,https://blogs.microsoft.com/blog/2026/06/24/inside-microsofts-two-decade-push-to-cut-water-intensity-while-scaling-for-growth/,official_technology_portfolio,global+US examples,Microsoft,owned fleet,cooling section,operating+technology,A,,Cooling share statement is Microsoft fleet not all US clouds
S017,Issued Air Permits for Data Centers,Virginia DEQ,2026-accessed,2026-08-11,https://www.deq.virginia.gov/news-info/shortcuts/permits/air/issued-air-permits-for-data-centers,government_permit_registry,US,AWS+Microsoft+others,Virginia facilities,permit registry,operating/design,A,,Registry proves facilities and generator permitting but not IT utilization
S018,2025年度国家绿色数据中心推荐工作通知,工业和信息化部等,2025-07-07,2026-08-11,https://www.miit.gov.cn/jgsj/jns/nyjy/art/2025/art_bc77dbe5b149458f83b9924c6ee95e84.html,government_standard_program,China,multiple providers,green DC applicants,eligibility criteria,policy_limit,A,,PUE<=1.30 is selection criterion not national average
S019,华为玉溪云计算数据中心验收公开信息,玉溪市政府,2017,2026-08-11,https://www.yuxi.gov.cn/yxszfxxgk/tzgg9999/20170524/570712.html,government_acceptance,China,Huawei,Yuxi facility,noise monitoring,operating,A,,Old facility; no exact monitoring dB values in summary
S020,China Mobile Yangtze Delta Wuhu EIA,芜湖市生态环境局,2026,2026-08-11,https://sthjj.wuhu.gov.cn/group4/M00/05/3F/rBwdT2gcVoqAawfYACPax8TdBSc880.pdf,government_EIA,China,China Mobile,Wuhu facility,noise table,design,A,,PDF contains source-level noise details; not portfolio average
S021,Google US datacenter locations for FedRAMP boundary,Google,2026-accessed,2026-08-11,https://knowledge.workspace.google.com/admin/compliance/google-workspace-fedramp-configuration-guide,official_location_list,US,Google,US datacenters,location section,operating,A,,Google Workspace boundary does not map one-to-one to Cloud region capacity
```

---

# 5. 表2：设施/项目级证据表

```csv
facility_id,provider,country,state_or_province,city,cloud_region,facility_owner,facility_operator,year,operating_or_design,construction_type_existing_capacity_retrofit_expansion_greenfield,it_capacity_mw,facility_power_mw,it_energy_mwh,facility_energy_mwh,pue,gpu_or_ai_share,server_or_gpu_type,utilization,capacity_boundary,chip_cooling,room_cooling,final_heat_rejection,cooling_share_basis,wue_value,wue_unit,wue_denominator,withdrawal_consumption_or_unspecified,annual_withdrawal_m3,annual_consumption_m3,cooling_makeup_m3,blowdown_m3,water_source,water_source_volume_m3,water_source_share,gross_floor_area_m2,it_white_space_m2,building_footprint_m2,site_area_m2,new_floor_area_m2,new_land_conversion_m2,outdoor_equipment_area_m2,continuous_noise_sources,noise_metric,noise_dba,reference_distance_m,operating_condition,boundary_noise_dba,mitigation,exact_evidence,derived_calculation,evidence_grade,limitations,source_id
CN_CT_WUHU_1,China Telecom,China,Anhui,Wuhu,NR,China Telecom,China Telecom,2023,design,greenfield,93.72,NR,NR,NR,NR,NR,NR,NR,"15620 racks x 6kW design",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,127000,NR,NR,NR,127000,NR,NR,"production equipment; backup generators",qualitative,NR,NR,design,"boundary compliance required","low-noise equipment; isolation; damping","一期15620个6kW机柜","15620*6kW=93.72MW; 127000/93.72=1355 m2/MW-IT",A,"Rack design capacity not actual IT load",S007
CN_CT_WUHU_TOTAL,China Telecom,China,Anhui,Wuhu,NR,China Telecom,China Telecom,2023,design,greenfield,187.44,NR,NR,NR,NR,NR,NR,NR,"31240 racks x 6kW design",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,253600,NR,NR,NR,253600,NR,NR,NR,NR,NR,NR,design,NR,NR,"总建筑面积253600平方米","31240*6kW=187.44MW; 253600/187.44=1353 m2/MW-IT",A,"Full campus design",S007
CN_CU_JJJ_NORTH,China Unicom,China,Tianjin,Wuqing,NR,China Unicom,China Unicom,2025,design,existing_campus_expansion,115,145,NR,NR,1.26,NR,NR,NR,"IT load 115MW; basic power 145MW",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,">100000",NR,NR,36000,">100000",0,NR,NR,NR,NR,NR,design,NR,NR,"北区占地54亩、建筑面积逾10万平方米","site=54*666.67/115=313 m2/MW-IT; floor>870 m2/MW-IT; design power ratio 145/115=1.26",B,"PUE calculation is inferred from design power ratio and should not be treated as operating PUE",S008
CN_ALI_HEYUAN,Alibaba Cloud,China,Guangdong,Heyuan,NR,Alibaba,Alibaba Cloud,2024,design,expansion,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,125395.44,NR,NR,100260.89,NR,0,NR,"cooling/electrical equipment; backup generators",qualitative,NR,NR,design,NR,"layout; silencing","改扩建后82台2000kW备用柴油发电机",NR,A,"IT MW unavailable; cannot derive area intensity",S009
CN_HUAWEI_WLCB,Huawei Cloud,China,Inner Mongolia,Ulanqab,NR,Huawei,Huawei Cloud,2020,operating,existing_facility,NR,NR,NR,NR,1.22,NR,NR,NR,"monthly PUE during free cooling",NR,"chilled-water/free cooling","cooling tower + plate heat exchanger / natural cooling",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,35000,NR,NR,NR,NR,NR,NR,"chillers; pumps; cooling towers",NR,NR,NR,"wet bulb <=10C free-cooling mode",NR,NR,"全年约10个月自然冷源; 月度PUE约1.22",NR,B,"1.22 is monthly free-cooling-mode PUE, not annual PUE",S006
CN_AWS_ZHONGWEI,AWS China,China,Ningxia,Zhongwei,cn-northwest-1,local AWS China facility entity,local operator,2019,design,greenfield,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,room air cooling,"low-noise condenser fans",air-cooled condenser,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,"external condenser fans; backup generators",qualitative,NR,NR,design,NR,"silencers; low-noise fans; vibration isolation","外部设备区安装低噪声冷凝器风扇",NR,A,"Older project; no capacity or WUE",S010
US_MS_SJ04,Microsoft,US,California,San Jose,Azure physical facility mapping NR,Microsoft,Microsoft,2025,design,greenfield,76.8,92.2,NR,NR,1.20,NR,NR,"expected total facility load 60-80% of design","critical IT design load 76.8MW",NR,"AHUs with cooling coils","hybrid closed-circuit fluid coolers; dry mode + adiabatic/evaporative assist",project design,1.25,L/kWh-IT,"derived from recycled cooling makeup / design IT energy",withdrawal_or_makeup_design,NR,NR,838767,NR,"recycled water for cooling; potable water only domestic",838767,">99% of design operational water excluding irrigation is reclaimed",58648,NR,NR,90205,58648,90205,NR,"roof fluid coolers; mechanical equipment",boundary SPL prediction,57.3,NR,"normal/no generators","57.3 normal; 62.7 generators operating","40-ft rooftop screen/parapet provides sound attenuation","76.8 MW critical IT; annual design PUE 1.20; 680 AFY recycled cooling water","floor=631278ft2*0.092903=58648m2=764m2/MW-IT; site=22.29acre=90205m2=1175m2/MW-IT; WUE=680AFY*1233.48m3/AF*1000/672.768M kWh=1.25 L/kWh",A,"All values are design, not operation; cloud region mapping not publicly proven",S011;S012;S013;S014
US_GOOGLE_DOUGLAS,Google,US,Georgia,Douglas County,NR,Google,Google,2025,operating,existing_facility,NR,NR,NR,NR,1.09,NR,NR,NR,"TTM PUE",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"Q4 2025 TTM PUE 1.09",NR,A,"Google facility serves multiple Google products; WUE not US-facility-disclosed here",S003
US_GOOGLE_LOUDOUN1,Google,US,Virginia,Loudoun County,NR,Google,Google,2025,operating,existing_facility,NR,NR,NR,NR,1.08,NR,NR,NR,"TTM PUE",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"Q4 2025 TTM PUE 1.08",NR,A,"WUE NR",S003
US_GOOGLE_NEWALBANY,Google,US,Ohio,New Albany,NR,Google,Google,2025,operating,existing_facility,NR,NR,NR,NR,1.06,NR,NR,NR,"TTM PUE Central Ohio New Albany",NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"Q4 2025 TTM PUE 1.06",NR,A,"Current Google page uses Central Ohio naming; physical Google Cloud-only share NR",S003
US_AWS_NVA,AWS,US,Virginia,Northern Virginia,us-east-1,AWS,AWS,2025,operating,portfolio_region,NR,NR,NR,NR,1.15,NR,NR,NR,"regional operating portfolio",NR,mixed,mixed,NR,0.06,L/kWh-IT,IT electricity,withdrawal,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"PUE 1.15; WUE 0.06",NR,A,"No facility count/IT MW or cooling shares",S001
US_AWS_OHIO,AWS,US,Ohio,Ohio,us-east-2,AWS,AWS,2025,operating,portfolio_region,NR,NR,NR,NR,1.12,NR,NR,NR,"regional operating portfolio",NR,mixed,mixed,NR,0.06,L/kWh-IT,IT electricity,withdrawal,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"PUE 1.12; WUE 0.06",NR,A,"No facility count/IT MW or cooling shares",S001
US_AWS_NCAL,AWS,US,California,Northern California,us-west-1,AWS,AWS,2025,operating,portfolio_region,NR,NR,NR,NR,1.18,NR,NR,NR,"regional operating portfolio",NR,mixed,mixed,NR,0.39,L/kWh-IT,IT electricity,withdrawal,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"PUE 1.18; WUE 0.39",NR,A,"No water-source shares",S001
US_AWS_OREGON,AWS,US,Oregon,Oregon,us-west-2,AWS,AWS,2025,operating,portfolio_region,NR,NR,NR,NR,1.12,NR,NR,NR,"regional operating portfolio",NR,mixed,mixed,NR,0.12,L/kWh-IT,IT electricity,withdrawal,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,operating,NR,NR,"PUE 1.12; WUE 0.12",NR,A,"No water-source shares",S001
```

---

# 6. 重点项目推导说明

## 6.1 Microsoft San José Data Center 04

这是目前找到的最完整美国商业云设施物理项目证据之一。

监管文件披露：

```text
Critical IT design load = 76.8 MW
Annual average-condition facility demand = 92.2 MW
Annual design PUE = 92.2 / 76.8 = 1.20
Worst-day facility demand = 97.8 MW
Peak PUE = 1.27
```

项目两栋四层数据中心：

```text
315,639 ft2/building × 2
= 631,278 ft2
= 58,648 m2
```

因此：

```text
gross floor intensity
= 58,648 / 76.8
≈ 764 m2 / MW-IT
```

场址：

```text
22.29 acres
= 90,205 m2
```

因此：

```text
site intensity
≈ 1,175 m2 / MW-IT
```

该项目设计冷却链：

```text
server/data hall
→ indoor AHU cooling coils
→ cooling-water loop
→ rooftop hybrid closed-circuit fluid coolers
→ dry sensible heat rejection when conditions allow
→ recycled-water adiabatic/evaporative assist when required
```

这是一个重要案例，因为它说明：

> “fluid cooler / closed circuit”不等于零水耗。

项目设计每年约：

```text
680 acre-feet recycled water for mechanical cooling
10.2 acre-feet reclaimed water for irrigation
1.35 acre-feet potable domestic water
```

680 AFY约为：

```text
838,767 m3/year
```

按76.8 MW设计IT负荷全年满载推导：

```text
design cooling withdrawal-WUE proxy
≈ 1.25 L/kWh-IT
```

该值**不是实际运营WUE**，不能用于美国平均，只用于展示湿式/混合冷却的项目级水量。

噪声预测：

```text
normal operation, generators off:
57.3 dBA at southwestern property line

generators operating:
62.7 dBA
```

应急发电机仅测试/维护短时运行，并不是全年连续噪声源。

---

# 7. 表3：供应商—国家—年度组合表

```csv
provider,country,year,facility_count,it_capacity_mw,it_energy_mwh,facility_energy_mwh,pue,wue_l_per_kwh_it,annual_site_water_m3,freshwater_share,reclaimed_water_share,cooling_technology_shares,existing_capacity_share,expansion_share,greenfield_share,aggregation_method,weight_variable,coverage,evidence_grade,limitations,source_ids
AWS,US,2025,NR,NR,NR,NR,1.135,0.09,NR,NR,NR,NR,NR,NR,NR,"unweighted median of four published US AWS regions","region, not IT energy","4 US AWS regions",B,"Official region values but no IT MW/energy weights; median is derived, not AWS official US average",S001
AWS,China,2025,NR,NR,NR,NR,1.25,NR,NR,NR,NR,NR,NR,NR,NR,"official AWS China geography portfolio",NR,"AWS China geography; Ningxia region disclosed",A,"China WUE not published",S001
Google,US,2025,"20+ disclosed US campuses",NR,NR,NR,"~1.09-1.10 typical; facility range about 1.04-1.15",NR,NR,NR,NR,NR,NR,NR,NR,"facility-level observable sample; no IT weighting",NR,"Google US campuses with >=12 months data",A,"Not a Google Cloud-only load allocation; country IT energy NR",S003;S021
Microsoft,US,2025,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,"No US-only portfolio metric published",NR,"US is embedded in Americas",A,"Americas PUE=1.16 WUE=0.34 cannot be relabeled US",S002
Microsoft,Americas,2025,NR,NR,NR,NR,1.16,0.34,NR,NR,NR,NR,NR,NR,NR,"official regional portfolio","owned-and-controlled facilities operational 12 months","Americas",A,"Regional reference only; not US average",S002
Alibaba Cloud,China,2024,NR,NR,NR,NR,1.20,NR,NR,NR,NR,NR,NR,NR,NR,"company self-built datacenter portfolio",NR,"self-built Alibaba Cloud data centers",B,"Public article does not provide China-only IT energy weighting; do not call China national average",S004
Tencent,China,2025,NR,NR,NR,NR,1.246,NR,NR,NR,NR,NR,NR,NR,NR,"company owned datacenter portfolio",NR,"owned Tencent data centers",B,"Country-specific IT denominator not disclosed",S005
Huawei Cloud,China,2020,1,NR,NR,NR,1.22,NR,NR,NR,NR,"cooling tower + plate HX + long seasonal free cooling",NR,NR,NR,"single operating facility/mode",NR,"Wulanchabu cloud-service DC",B,"1.22 is natural-cooling-mode monthly PUE; not annual or national",S006
China Telecom,China,2023,1,93.72,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,1,"single design project",IT rack design MW,"Wuhu phase1",A,"Design facility; PUE/WUE NR",S007
China Unicom,China,2025,1,115,NR,NR,"1.26 design facility/IT ratio proxy",NR,NR,NR,NR,NR,NR,1,0,"single campus expansion project","design IT MW","Jing-Jin-Ji north zone",B,"Ratio is not observed annual PUE",S008
Oracle Cloud,US,2024-2026,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,NR,"not aggregated","NR","insufficient country-specific physical disclosures",C,"Excluded from final numerical sample",NR
```

---

# 8. PUE结果

## 8.1 美国

直接商业云运营证据：

### AWS 2025

```text
Northern Virginia 1.15
Ohio              1.12
Northern California 1.18
Oregon            1.12
```

四Region非加权中位数：

```text
median = (1.12 + 1.15)/2
       = 1.135
```

### Google

2025年美国披露园区大量TTM PUE约：

```text
1.04–1.15
```

多数成熟园区集中约：

```text
1.08–1.12
```

### Microsoft

FY25 Americas：

```text
PUE = 1.16
```

但不可重命名为US。

因此推荐：

```text
US cloud observable scenario:
1.09 / 1.13 / 1.18
```

---

## 8.2 中国

运营组合：

```text
Alibaba Cloud self-built 2024 = 1.200
Tencent owned 2025          = 1.246
AWS China 2025              = 1.25
```

设施模式：

```text
Huawei Wulanchabu free-cooling monthly PUE ≈1.22
```

因此：

```text
China cloud observable scenario:
1.20 / 1.24 / 1.25
```

不能将工信部绿色数据中心：

```text
PUE <= 1.30
```

这一申报限值作为实际平均。

---

# 9. WUE与现场水

## 9.1 AWS是目前口径最清楚的美国商业云样本

AWS明确：

```text
WUE = liters of water withdrawn / kWh of IT load
```

因此这里的WUE是**取水型WUE**，不是净耗水WUE。

2025：

```text
Virginia   0.06
Ohio       0.06
N.Cal      0.39
Oregon     0.12 L/kWh-IT
```

推荐：

```text
US withdrawal-WUE:
0.06 / 0.12 / 0.39 L/kWh-IT
```

这些都是实际运营Region数据。

## 9.2 Microsoft的口径不同

Microsoft：

```text
annual liters used for humidification and cooling
/
annual IT electricity
```

FY25 Americas：

```text
0.34 L/kWh-IT
```

“used”并未在该页面明确拆成withdrawal与consumption，因此不能与AWS 0.34进行严格同口径合并。

## 9.3 中国

没有找到满足以下全部条件的2024–2026公开组合：

```text
中国境内
+ 大型商业云
+ 实际年度
+ onsite water
+ IT-energy denominator
+ clear WUE definition
```

因此：

```text
China cloud national/portfolio WUE = NR
```

项目级和历史数据可以用于技术范围，但不得替代全国平均。

---

# 10. 水源

## 美国

Microsoft SJDC04设计值：

```text
cooling water: reclaimed water
irrigation: reclaimed water
domestic: potable water
```

设计体积显示该项目水量几乎全部来自再生水。

但是：

```text
one Microsoft project
!= US cloud reclaimed-water share
```

Microsoft还公开在Texas、Washington、California等地区扩大再生/回用水使用，AWS和Google也有地方项目，但缺少统一分母。

因此：

```text
US freshwater share = NR
US reclaimed water share = NR
```

## 中国

部分中国数据中心实际或政策性使用：

- 再生水；
- 市政水；
- 个别项目自然水体/湖水冷却；
- 非常规水。

但没有云商中国组合的水源体积份额。

因此：

```text
China freshwater share = NR
China reclaimed water share = NR
```

---

# 11. 冷却与最终排热

## 11.1 美国可见的技术迁移

Microsoft提供了很好的技术时间序列：

### 传统/现有设施

大量设施采用：

```text
direct air cooling
+
evaporative assist above 29.4°C
```

### 2024年后新设计

Microsoft宣布自2024年8月起，新数据中心设计转向：

```text
direct-to-chip closed-loop liquid cooling
+
air-cooled chillers / mechanical heat rejection
+
zero water evaporation for cooling
```

Microsoft 2026披露约90%的2025 owned fleet采用高效低水/零水冷却体系，但这仍不能分解成“美国所有商业云干式占多少%”。

### Microsoft SJDC04

则代表另一条混合路径：

```text
AHUs
→ closed water loop
→ hybrid closed-circuit fluid cooler
→ dry mode when possible
→ reclaimed-water evaporative assist as needed
```

因此即使同一家云商，不同代际、地点的最终排热也不同。

---

## 11.2 中国

乌兰察布华为云案例：

```text
cooling tower
+
plate heat exchanger
+
seasonal free cooling
```

低湿球温度下冷机停机，全年约10个月利用自然冷源。

AWS中卫环评显示存在低噪声室外冷凝器风扇，属于空气最终排热的项目证据。

因此中国同样不存在统一的“云数据中心=冷却塔”或“云数据中心=风冷”路线。

---

## 11.3 技术份额

由于没有公开按：

```text
IT MW
或
IT MWh
```

统计的技术容量份额，两国均：

```text
dry/air heat-rejection share = NR
wet/evaporative share        = NR
```

不得根据Microsoft技术路线、单个华为案例或地区气候自行生成全国百分比。

---

# 12. 建筑与土地

## 12.1 中国可观测项目

### China Telecom Wuhu

一期：

```text
IT = 15,620 × 6 kW
   = 93.72 MW

GFA = 127,000 m2

GFA intensity
= 1,355 m2/MW-IT
```

全项目：

```text
187.44 MW IT
253,600 m2
≈1,353 m2/MW-IT
```

### China Unicom Jing-Jin-Ji North

```text
IT load = 115 MW
site = 54 mu ≈36,000 m2
GFA >100,000 m2
```

因此：

```text
site intensity ≈313 m2/MW-IT
GFA intensity >870 m2/MW-IT
```

两个商业运营商样本给出的建筑强度范围约：

```text
870–1,355 m2/MW-IT
```

若用两个项目的已知容量和保守100,000m2值合计：

```text
(127000 + 100000)/(93.72 + 115)
≈1,088 m2/MW-IT
```

所以可建立：

```text
China GFA sample scenario:
Low  = 870
Base = 1,100
High = 1,355 m2/MW-IT
```

这不是全国平均。

场址面积只有一个可直接匹配IT MW的商业云/运营商样本，因此：

```text
China site intensity:
Low = NR
Base proxy = 313 m2/MW-IT
High = NR
```

---

## 12.2 美国Microsoft SJDC04

设计：

```text
GFA ≈58,648 m2
IT  =76.8 MW
site≈90,205 m2
```

得到：

```text
GFA ≈764 m2/MW-IT
site≈1,175 m2/MW-IT
```

该项目位于高土地价值、四层数据中心设计，与单层郊区园区不能直接互换。

因此美国没有足够商业云设施样本构成low/base/high面积分布，建议：

```text
US GFA intensity:
Low  = NR
Base single-facility proxy = 764 m2/MW-IT
High = NR

US site intensity:
Low  = NR
Base single-facility proxy = 1,175 m2/MW-IT
High = NR
```

---

# 13. 新增容量实现方式

## 13.1 已有容量/改造

公开证据表明云厂商可以在既有数据中心部署新的液冷AI机架，并使用rack-level heat exchanger等方式兼容既有air-cooled环境。

因此新增AI需求并不总对应立即新建数据中心。

## 13.2 既有园区扩建

中国案例：

- 阿里河源为明确改扩建；
- 联通京津冀北区属于园区新增项目；
- 数据中心运营商常按多期、多栋建设。

这种情况下：

```text
new_floor_area > 0
new_land_conversion may = 0
```

如果土地已包含在原园区储备用地。

## 13.3 绿地新建

Microsoft San José SJDC04：

```text
previously largely vacant site
22.29 acres
2 new datacenter buildings
new cooling
new substation/switchyard
new water infrastructure
```

是明确greenfield案例。

## 13.4 为什么不能给三种建设方式平均份额？

没有任何主要云厂商公开：

```text
X% AI demand served by spare existing capacity
Y% by existing-campus expansion
Z% by greenfield
```

因此：

```text
existing_capacity_share = NR
expansion_share         = NR
greenfield_share        = NR
```

建模时应直接跑三个建设情景，而不是假设权重。

---

# 14. 噪声

## 14.1 美国设施级高质量证据

Microsoft SJDC04：

```text
ambient = 51–59 dBA

southwestern property line:
normal operation / generators off = 57.3 dBA
generators operating             = 62.7 dBA
```

备用发电机：

```text
anticipated testing ≈8 h/year
permit limit <=50 h/year/generator
otherwise emergency only
```

因此绝不能把62.7 dBA按8760小时连续运行。

项目采用40英尺高屋顶屏障/女儿墙遮蔽机械电气设备并提供声学衰减。

## 14.2 中国

华为玉溪云计算中心验收资料明确：

- 噪声源包括机房、冷却塔、备用发电机、排风风机；
- 实测昼夜厂界均满足相应标准。

但摘要没有公开具体监测dBA，因此：

```text
noise_dba = NR
```

中国电信/移动芜湖环评也确认柴油机和生产设备为噪声源并要求隔声、消声、减振，但公开摘要不足以形成“中国云平均dB”。

因此：

> 两国都不应生成“云数据中心平均噪声dBA”。

噪声应作为设施选址与项目约束，而非国家平均参数。

---

# 15. AI/GPU负荷、利用率与超配

这一块是本轮最大的物理数据缺口。

公开资料没有给出可用于模型的：

```text
AI/GPU electricity / total IT electricity
GPU average physical utilization
server average utilization
multi-tenant oversubscription
capacity reserve
GPU idle ratio
```

AWS只定性披露规模化云能够提高资源利用率。

Microsoft SJDC04监管文件则明确指出，设计容量往往不会完全达到，经验上设施需求约为设计的：

```text
60–80%
```

但这是**项目总需求相对设计负荷**，不是GPU利用率。

因此：

```text
cloud_GPU_utilization = NR
```

不得从AWS“up to 4.1× efficiency”、云市场份额或实例价格反推利用率。

在“完成相同AI服务”的模型里，物理GPU工作量仍应由独立推理benchmark确定，而不是通过PUE/WUE研究反推出。

---

# 16. 表4：中国—美国最终参数表

```csv
country,parameter,low,base,high,unit,year_range,aggregation_method,weight_variable,sample_facilities,sample_providers,covered_it_capacity_mw,market_coverage_status,evidence_grade,recommended_model_use,prohibited_interpretation,source_ids
China,PUE,1.20,1.24,1.25,PUE,2024-2025,"Method D observable cloud/provider operating sample","none; no IT-energy weights","Alibaba/Tencent portfolios; Huawei facility; AWS China cross-check","Alibaba Cloud; Tencent; Huawei Cloud; AWS China",NR,unknown,B,"cloud facility electricity multiplier sensitivity","not China national weighted average",S001;S004;S005;S006
US,PUE,1.09,1.13,1.18,PUE,2025,"Method D US commercial-cloud facility/region sample","none; no cross-provider IT-energy weights","AWS 4 US regions; Google US campuses; Microsoft Americas cross-check","AWS; Google; Microsoft",NR,unknown,A-/B+,"cloud facility electricity multiplier sensitivity","not IT-energy-weighted US national average",S001;S002;S003
China,onsite_WUE,NR,NR,NR,L/kWh-IT,2024-2026,"insufficient representative country-specific operating data",NR,NR,"major Chinese clouds",NR,unknown,C,"do not use national single value; facility/cooling scenarios only","do not import global company WUE",S004;S005;S006
US,onsite_withdrawal_WUE,0.06,0.12,0.39,L/kWh-IT,2025,"Method D AWS US-region observed range","no IT-MWh weighting","4 AWS US regions","AWS",NR,unknown,A,"US onsite withdrawal-WUE sensitivity","not all-US-cloud average; not consumption WUE",S001
US,Microsoft_Americas_WUE_reference,0.34,0.34,0.34,L/kWh-IT,FY2025,"official Americas portfolio reference","owned/controlled portfolio","Americas","Microsoft",NR,not_US_only,A,"cross-check only","must not rename Americas as United States",S002
China,freshwater_share,NR,NR,NR,fraction,2024-2026,"insufficient national/provider data",NR,project examples,NR,NR,unknown,C,"facility-specific water source only","no national average",S006;S009
US,freshwater_share,NR,NR,NR,fraction,2024-2026,"insufficient national/provider data",NR,"Microsoft SJ04 and other local projects","Microsoft",NR,unknown,C,"facility-specific scenario only","SJ04 reclaimed share not US share",S013
China,reclaimed_water_share,NR,NR,NR,fraction,2024-2026,"insufficient country portfolio denominator",NR,project examples,NR,NR,unknown,C,"use project/source-specific data","no inferred national share",NR
US,reclaimed_water_share,NR,NR,NR,fraction,2024-2026,"insufficient country portfolio denominator",NR,"SJDC04 design example","Microsoft",76.8,negligible_market_coverage,C,"location-specific scenario","99%+ SJ04 design reclaimed share cannot represent US cloud",S013
China,dry_or_air_heat_rejection_share,NR,NR,NR,fraction,2024-2026,"no capacity-weighted technology inventory",NR,"AWS Zhongwei; Huawei Wulanchabu etc.","multiple",NR,unknown,C,"categorical cooling scenarios","do not infer from liquid cooling label",S006;S010
China,wet_or_evaporative_heat_rejection_share,NR,NR,NR,fraction,2024-2026,"no capacity-weighted technology inventory",NR,"Huawei Wulanchabu and other facility cases","multiple",NR,unknown,C,"categorical cooling scenarios","no national percentage",S006
US,dry_or_air_heat_rejection_share,NR,NR,NR,fraction,2024-2026,"no country capacity-weighted inventory",NR,"Microsoft technology generations","Microsoft",NR,unknown,C,"dry-dominant scenario for new designs if specifically modeled","Microsoft fleet technology not all US cloud",S015;S016
US,wet_or_evaporative_heat_rejection_share,NR,NR,NR,fraction,2024-2026,"no country capacity-weighted inventory",NR,"SJDC04; legacy Microsoft fleet","Microsoft",NR,unknown,C,"wet/mixed scenario","no US national share",S012;S016
China,gross_floor_area_intensity,870,1100,1355,m2/MW-IT,2023-2025,"Method D design-project sample; base approximately capacity-aggregated two known projects","design IT MW","China Telecom Wuhu; China Unicom JJJ","China Telecom; China Unicom",208.72,unknown,B,"cloud infrastructure land/building scenario","not occupied white-space intensity; not national average",S007;S008
China,site_area_intensity,NR,313,NR,m2/MW-IT,2025,"single facility proxy","design IT MW","China Unicom JJJ north zone","China Unicom",115,unknown,C,"optional site-area proxy","do not treat as national average",S008
US,gross_floor_area_intensity,NR,764,NR,m2/MW-IT,2025,"single commercial-cloud design facility proxy","critical IT design MW","Microsoft SJDC04","Microsoft",76.8,unknown,C,"US greenfield multistory proxy","not US average; high-rise California design",S011;S012
US,site_area_intensity,NR,1175,NR,m2/MW-IT,2025,"single commercial-cloud design facility proxy","critical IT design MW","Microsoft SJDC04","Microsoft",76.8,unknown,C,"US greenfield site proxy","not US average",S011;S012
China,existing_capacity_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"retrofit evidence exists but shares unavailable","multiple",NR,unknown,C,"run explicit existing-capacity scenario","do not guess portfolio fraction",S009
China,expansion_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"Alibaba Heyuan; Unicom JJJ expansion","Alibaba; Unicom",NR,unknown,C,"run explicit campus-expansion scenario","do not infer from project counts",S008;S009
China,greenfield_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"China Telecom Wuhu etc.","China Telecom",93.72,unknown,C,"run explicit greenfield scenario","not actual portfolio share",S007
US,existing_capacity_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"existing-facility liquid cooling deployment evidence","Microsoft/Google",NR,unknown,C,"run retrofit/spare-capacity scenario","do not assign probability",S015
US,expansion_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"campus expansion evidence exists","AWS/Google/Microsoft",NR,unknown,C,"run campus-expansion scenario","not actual share",NR
US,greenfield_share,NR,NR,NR,fraction,2024-2026,"no observed weighting",NR,"Microsoft SJDC04 greenfield","Microsoft",76.8,unknown,C,"run greenfield scenario","not actual portfolio share",S011
China,GPU_or_AI_share_of_IT,NR,NR,NR,fraction,2024-2026,"not disclosed",NR,NR,"major clouds",NR,unknown,C,"leave endogenous to AI-service model","do not infer from AI revenue",NR
US,GPU_or_AI_share_of_IT,NR,NR,NR,fraction,2024-2026,"not disclosed",NR,NR,"AWS/Azure/Google",NR,unknown,C,"leave endogenous","do not infer from GPU instance count or AI revenue",NR
China,physical_GPU_utilization,NR,NR,NR,fraction,2024-2026,"not publicly disclosed",NR,NR,"major clouds",NR,unknown,C,"sensitivity only if external benchmark exists","no market-share proxy",NR
US,physical_GPU_utilization,NR,NR,NR,fraction,2024-2026,"not publicly disclosed",NR,NR,"AWS/Azure/Google",NR,unknown,C,"sensitivity only","AWS scale-efficiency claim is not utilization telemetry",S001
```

---

# 17. 推荐模型参数

## 17.1 如果模型当前必须给PUE

推荐：

```text
China cloud:
Low/Base/High = 1.20 / 1.24 / 1.25

US cloud:
Low/Base/High = 1.09 / 1.13 / 1.18
```

二者均应标：

```text
aggregation_method = Method D
```

不是全国IT电量加权平均。

---

## 17.2 美国现场WUE

推荐：

```text
0.06 / 0.12 / 0.39 L/kWh-IT
```

严格命名：

```text
AWS-US observed withdrawal-WUE scenario
```

而不是：

```text
US cloud water consumption
```

---

## 17.3 中国现场WUE

推荐：

```text
NR
```

如果PyPSA/环境模型必须运行水情景，则应该从**冷却架构**生成水需求：

```text
dry/air scenario
mixed-hybrid scenario
wet/evaporative scenario
```

而不是生成一个假中国平均WUE。

---

# 18. 建设情景建议

由于没有真实占比，建议三个情景分别计算。

## Scenario 1：existing capacity / retrofit

假设：

```text
new land conversion = 0
new gross floor area ≈ 0
```

但可能需要：

- 液冷换热设备；
- 配电升级；
- 室外冷却升级；
- 网络升级。

适合表达“短期云商利用现有余量吸收制造AI新增需求”。

## Scenario 2：existing campus expansion

```text
new building area > 0
new land conversion = 0 or small
```

如果使用已储备园区用地。

这是阿里河源、联通多期园区等常见扩展形式。

## Scenario 3：greenfield

完整计入：

```text
building
site
substation
backup generation
roads
cooling
water infrastructure
```

Microsoft SJDC04是高质量实例。

---

# 19. `II_1host`—中国云—美国云可比边界

| 项目 | II_1host行业集中自建 | 中国云采购 | 美国云采购 |
|---|---|---|---|
| 制造企业现场大型AI机房 | 有 | 无 | 无 |
| GPU服务器物理存在 | 自建中心 | 中国云DC | 美国云DC |
| IT电耗 | 自建中心 | 中国云DC | 美国云DC |
| PUE设施损失 | 自建中心 | 中国云DC | 美国云DC |
| 现场冷却水 | 自建中心 | 中国云DC | 美国云DC |
| 建筑土地 | 自建中心 | 中国云DC | 美国云DC |
| 数据中心噪声 | 自建中心 | 中国云DC | 美国云DC |
| 制造厂现场新增噪声 | 取决于II_1host位置 | ≈0 | ≈0 |
| 发电侧水耗 | **本研究全部排除** | **排除** | **排除** |
| GPU实际物理利用率 | 需独立建模 | NR | NR |
| 云商账单 | 无 | 有 | 有 |

关键原则：

> 云采购只是改变设施所在地和资产所有者，不改变AI计算需要物理服务器这一事实。

---

# 20. 被排除或不进入国家平均的来源

| 来源类型 | 处理 | 原因 |
|---|---|---|
| Meta自用数据中心 | 仅技术参照 | 不销售通用GPU-IaaS |
| 托管/批发DC | 通常排除 | 无法证明AWS/Azure/Google具体租户边界 |
| IDC行业平均 | 仅背景 | 不等于商业大型云 |
| Microsoft Americas | 仅美国交叉验证 | Americas≠US |
| Microsoft Asia Pacific | 不作为中国 | Asia Pacific≠China |
| Alibaba/Tencent全球或地域不清组合 | 保留但降级 | 不能证明中国国别权重 |
| 设计PUE/WUE | 项目设计表保留 | 不作为运营平均 |
| 政策PUE<=1.30 | 仅限值 | 不是实际运行值 |
| 最优案例PUE 1.09等 | 项目证据 | 不作为全国平均 |
| 搜索摘要/新闻中的用水争议 | 线索 | 非原始量化证据 |
| 云收入/市场份额 | 完全禁止用于权重 | 不是IT MW或IT MWh |

---

# 21. 数据缺口

## 21.1 云商真实GPU利用率

**未找到。**

最需要未来获得：

```text
GPU active fraction
SM utilization
HBM utilization
batching
idle fraction
physical host utilization
reserved capacity
```

这些比进一步优化PUE的小数点更可能影响同等AI服务的设备需求。

## 21.2 AI负荷占IT电量

**未找到。**

大型云商数据中心同时运行：

- AI
- CPU通用云
- storage
- networking
- SaaS/internal workloads

不能把整个数据中心PUE/WUE直接解释成AI负荷特征。

## 21.3 中国WUE

这是中国云物理模型最重要的数据缺口之一。

建议继续针对：

- 阿里张北/河源；
- 腾讯清远/怀来/贵安；
- 华为贵安/乌兰察布；
- 天翼云国家枢纽节点；
- 移动云呼和浩特/芜湖；
- 联通中卫/京津冀

逐个寻找：

```text
水资源论证
取水许可
环评全文
节水型数据中心申报材料
ESG facility table
```

## 21.4 水源份额

两国都缺：

```text
freshwater / reclaimed / groundwater
```

按国家组合的实际体积份额。

## 21.5 冷却技术容量份额

两国均有足够证据说明技术多样，但缺少容量权重。

## 21.6 边际新容量

没有厂商披露：

```text
AI新增1 MW需求中
多少来自existing spare capacity
多少来自retrofit
多少触发new build
```

这是将云采购映射到**边际建筑/土地影响**时最大的结构不确定性。

---

# 22. 最终结论

1. **中国：没有足够证据形成全国代表性大型商业云数据中心物理平均值。**
2. **美国：PUE和AWS式WUE有较强可观测运营样本，但仍不能形成跨厂商IT电量加权全国平均。**
3. 中国PUE建议使用`1.20/1.24/1.25`作为可观测样本情景。
4. 美国PUE建议使用`1.09/1.13/1.18`。
5. 美国现场withdrawal-WUE可使用AWS四个US Region的`0.06/0.12/0.39 L/kWh-IT`。
6. 中国现场WUE：`NR`，不应虚构平均值。
7. 两国淡水份额、再生水份额、干式/湿式最终排热容量份额均为`NR`。
8. 中国商业云/运营商项目建筑面积样本支持约`870–1355 m2/MW-IT`，Base约`1100 m2/MW-IT`，但不是全国平均。
9. 美国Microsoft SJDC04单项目设计代理约`764 m2/MW-IT`建筑面积和`1175 m2/MW-IT`场址。
10. 既有容量/扩建/绿地建设的实际权重两国均为`NR`，应作为三个独立情景。
11. 云商GPU实际物理利用率、多租户利用率和AI负荷份额全部`NR`，不得从收入或效率宣传反推。
12. 制造企业采购云服务后，制造厂现场大型AI设施影响可以接近零，但云商数据中心的服务器、电力、水、建筑、土地和噪声必须继续留在系统边界内。
