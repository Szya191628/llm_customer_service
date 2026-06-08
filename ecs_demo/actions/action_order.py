# -*- coding: utf-8 -*-
"""
订单相关Action

实现订单查询、修改收货信息、取消订单等功能。
适配app框架Action接口。
使用 goto 槽机制统一订单查询逻辑。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.agent.actions import Action, ActionResult

logger = logging.getLogger(__name__)


class ActionAskOrderId(Action):
    """
    统一的订单查询Action。
    根据 goto 槽的值决定查询条件：
    - action_ask_order_id_before_completed_3_days: 进行中或3日内已完成的订单
    - action_ask_order_id_before_delivered: 已签收之前的订单（可修改收货信息）
    - action_ask_order_id_before_shipped: 待发货之前的订单（可取消）
    - action_ask_order_id_shipped: 已发货的订单（查物流）
    - action_ask_order_id_shipped_delivered: 已发货和已签收的订单（投诉物流）
    - action_ask_order_id_after_delivered: 已签收后的订单（售后）
    """
    
    @property
    def name(self) -> str:
        return "action_ask_order_id"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo, OrderStatus
        from sqlalchemy.orm import joinedload
        from sqlalchemy import and_, or_
        
        result = ActionResult()
        user_id = tracker.get_slot("user_id") or "1001"
        goto = tracker.get_slot("goto")
        last_viewed_order_id = tracker.get_slot("last_viewed_order_id")
        page = int(tracker.get_slot("order_list_page") or 0)

        # 每页显示数量
        PAGE_SIZE = 5

        # 检查是否是分页请求
        latest_message = ""
        if tracker.latest_message:
            latest_message = tracker.latest_message.text

        is_pagination_request = False
        if "下一页" in latest_message:
            page = page + 1
            tracker.set_slot("order_list_page", page)
            is_pagination_request = True
        elif "上一页" in latest_message:
            page = max(0, page - 1)
            tracker.set_slot("order_list_page", page)
            is_pagination_request = True
        elif "第一页" in latest_message or "首页" in latest_message:
            page = 0
            tracker.set_slot("order_list_page", page)
            is_pagination_request = True

        # 如果是分页请求，清除 order_id 以避免误判
        if is_pagination_request:
            tracker.set_slot("order_id", None)

        try:
            with SessionLocal() as session:
                # 根据 goto 值构建查询条件
                query_condition = self._get_query_condition(user_id, goto)
                
                order_infos = (
                    session.query(OrderInfo)
                    .join(OrderInfo.order_status_)
                    .options(joinedload(OrderInfo.order_detail))
                    .filter(query_condition)
                    .order_by(OrderInfo.create_time.desc())
                    .all()
                )
                
                # 上下文关联：如果最近查看的订单在查询结果中，优先使用
                if last_viewed_order_id and last_viewed_order_id != "false":
                    matching_order = next(
                        (o for o in order_infos if o.order_id == last_viewed_order_id),
                        None
                    )
                    if matching_order:
                        # 自动选择最近查看的订单，跳过选择步骤
                        tracker.set_slot("order_id", matching_order.order_id)
                        sku_summary = ", ".join([
                            f"{od.sku_name}×{od.sku_count}"
                            for od in matching_order.order_detail[:2]
                        ])
                        if len(matching_order.order_detail) > 2:
                            sku_summary += f" 等{len(matching_order.order_detail)}件"

                        message = [
                            f"已自动选择最近查看的订单：",
                            f"[{matching_order.order_status}] {sku_summary}",
                            f"订单ID：{matching_order.order_id}",
                        ]
                        buttons = [
                            {"title": "确认", "payload": f"/SetSlots(order_id={matching_order.order_id})"},
                            {"title": "重新选择", "payload": "/SetSlots(order_id=false)"},
                        ]
                        result.add_response("\n".join(message), buttons=buttons)
                        return result

                order_nums = len(order_infos)

                # 没有订单
                if order_nums == 0:
                    result.add_response("暂无订单")
                    tracker.set_slot("order_id", "false")
                    # 设置 action_listen_rejected 标记，打断流程
                    result.reject_action_listen = True
                    return result

                # 只有一个订单，自动选择
                if order_nums == 1:
                    order_info = order_infos[0]
                    # 自动设置订单ID，跳过选择步骤
                    tracker.set_slot("order_id", order_info.order_id)
                    message = [
                        f"[{order_info.order_status}]**订单ID**：{order_info.order_id}",
                    ]
                    for order_detail in order_info.order_detail:
                        message.append(f"- {order_detail.sku_name} × {order_detail.sku_count}")

                    buttons = [
                        {
                            "title": "确认",
                            "payload": f"/SetSlots(order_id={order_info.order_id})",
                        },
                        {"title": "返回", "payload": "/SetSlots(order_id=false)"},
                    ]
                    result.add_response("\n".join(message), buttons=buttons)

                # 多个订单，分页显示
                else:
                    # 计算分页
                    start_idx = page * PAGE_SIZE
                    end_idx = start_idx + PAGE_SIZE
                    display_orders = order_infos[start_idx:end_idx]
                    total_pages = (order_nums + PAGE_SIZE - 1) // PAGE_SIZE

                    buttons = []
                    for order_info in display_orders:
                        # 简化显示：状态 + 商品摘要
                        sku_summary = ", ".join([
                            f"{od.sku_name}×{od.sku_count}"
                            for od in order_info.order_detail[:2]  # 最多显示2个商品
                        ])
                        if len(order_info.order_detail) > 2:
                            sku_summary += f" 等{len(order_info.order_detail)}件"

                        buttons.append({
                            "title": f"[{order_info.order_status}] {sku_summary}",
                            "payload": f"/SetSlots(order_id={order_info.order_id})",
                        })

                    # 分页提示
                    page_info = f"第{page + 1}页/共{total_pages}页（{order_nums}个订单）"

                    # 添加"查看更多"按钮（如果不是最后一页）
                    if end_idx < order_nums:
                        buttons.append({
                            "title": "查看更多 →",
                            "payload": "下一页",
                        })

                    # 添加"返回上一页"按钮（如果不是第一页）
                    if page > 0:
                        buttons.append({
                            "title": "← 上一页",
                            "payload": "上一页",
                        })

                    # 添加"返回首页"按钮（如果不是第一页）
                    if page > 0:
                        buttons.append({
                            "title": "返回首页",
                            "payload": "第一页",
                        })

                    buttons.append({"title": "返回", "payload": "/SetSlots(order_id=false)"})
                    result.add_response(f"请选择订单（{page_info}）", buttons=buttons)
                    
        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            result.add_response("查询订单时出错，请稍后重试。")
        
        return result
    
    def _get_query_condition(self, user_id: str, goto: Optional[str]):
        """根据 goto 值构建查询条件"""
        from actions.db_table_class import OrderInfo, OrderStatus
        from sqlalchemy import and_, or_
        
        match goto:
            case "action_ask_order_id_shipped":
                # 查询已发货的订单
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status == "已发货",
                )
            case "action_ask_order_id_shipped_delivered":
                # 查询已发货和已签收的订单
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status.in_(["已发货", "已签收"]),
                )
            case "action_ask_order_id_before_completed_3_days":
                # 查询进行中，或3日内已完成的订单
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status != "已取消",
                    or_(
                        OrderInfo.order_status != "已完成",
                        OrderInfo.complete_time > datetime.now() - timedelta(days=3),
                    ),
                )
            case "action_ask_order_id_before_delivered":
                # 查询已签收之前状态的订单（可修改收货信息）
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status != "已取消",
                    OrderStatus.status_code <= 320,
                )
            case "action_ask_order_id_before_shipped":
                # 查询已发货之前状态的订单（可取消）
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status != "已取消",
                    OrderStatus.status_code <= 310,
                )
            case "action_ask_order_id_after_delivered":
                # 查询已签收、售后中、已完成的订单（售后）
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status != "已取消",
                    OrderStatus.status_code >= 330,
                )
            case _:
                # 默认：查询所有非取消订单
                return and_(
                    OrderInfo.user_id == user_id,
                    OrderInfo.order_status != "已取消",
                )


class ActionGetOrderDetail(Action):
    """获取订单详情"""
    
    @property
    def name(self) -> str:
        return "action_get_order_detail"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo, Postsale
        from sqlalchemy.orm import joinedload
        from sqlalchemy import and_, func
        
        result = ActionResult()
        order_id = tracker.get_slot("order_id")
        
        if not order_id or order_id == "false":
            result.add_response("未找到该订单，请检查订单号是否正确。")
            return result
        
        try:
            with SessionLocal() as session:
                order_info = (
                    session.query(OrderInfo)
                    .options(joinedload(OrderInfo.order_detail))
                    .options(joinedload(OrderInfo.logistics))
                    .options(joinedload(OrderInfo.receive))
                    .options(joinedload(OrderInfo.order_status_))
                    .filter_by(order_id=order_id)
                    .first()
                )
                
                if not order_info:
                    result.add_response("未找到该订单，请检查订单号是否正确。")
                    return result
                
                # 保存最近查看的订单ID（用于上下文关联）
                tracker.set_slot("last_viewed_order_id", order_info.order_id)

                # 拼接订单信息
                message = [f"- [{order_info.order_status}]**订单ID**：{order_info.order_id}"]

                # 时间信息
                for k, v in {
                    "创建时间": order_info.create_time,
                    "支付时间": order_info.payment_time,
                    "签收时间": order_info.delivered_time,
                    "完成时间": order_info.complete_time,
                }.items():
                    if v:
                        message.append(f"  - {k}：{v}")
                
                # 订单明细
                message.append("- **订单明细**：")
                total_total_amount = 0.0
                total_discount_amount = 0.0
                total_final_amount = 0.0
                for order_detail in order_info.order_detail:
                    message.append(
                        f"  - {order_detail.sku_name} × {order_detail.sku_count} | "
                        f"{order_detail.total_amount}-{order_detail.discount_amount}={order_detail.final_amount}"
                    )
                    total_total_amount += float(order_detail.total_amount)
                    total_discount_amount += float(order_detail.discount_amount)
                    total_final_amount += float(order_detail.final_amount)
                message.append(
                    f"  - **合计**：{total_total_amount}-{total_discount_amount}={total_final_amount}"
                )
                
                # 收货信息
                message.extend([
                    "- **收货信息**：",
                    f"  - 收货人：{order_info.receive.receiver_name}",
                    f"  - 联系电话：{order_info.receive.receiver_phone}",
                    f"  - 收货地址：{order_info.receive.receive_province}"
                    f"{order_info.receive.receive_city}"
                    f"{order_info.receive.receive_district}"
                    f"{order_info.receive.receive_street_address}",
                ])
                
                # 最近物流信息
                logistics = order_info.logistics
                if logistics:
                    message.append("- **最近物流信息**：")
                    message.append(f"  - {logistics[0].logistics_tracking.splitlines()[-1]}")
                
                result.add_response("\n".join(message))
                
                # 检查是否有售后信息（status_code >= 400）
                if order_info.order_status_.status_code >= 400:
                    # 查询售后信息
                    order_detail_ids = [
                        order_detail.order_detail_id for order_detail in order_info.order_detail
                    ]
                    
                    # 子查询：每个订单详情的最新售后
                    subquery = (
                        session.query(
                            Postsale.order_detail_id,
                            func.max(Postsale.create_time).label("max_time"),
                        )
                        .filter(Postsale.order_detail_id.in_(order_detail_ids))
                        .group_by(Postsale.order_detail_id)
                        .subquery()
                    )
                    
                    postsales = (
                        session.query(Postsale)
                        .join(
                            subquery,
                            and_(
                                Postsale.order_detail_id == subquery.c.order_detail_id,
                                Postsale.create_time == subquery.c.max_time,
                            ),
                        )
                        .options(joinedload(Postsale.order_detail))
                        .options(joinedload(Postsale.logistics))
                        .all()
                    )
                    
                    if postsales:
                        for postsale in postsales:
                            ps_message = [
                                f"- [{postsale.postsale_status}]**售后ID**：{postsale.postsale_id}"
                            ]
                            ps_message.append("- **订单明细**：")
                            ps_message.append(
                                f"  -{postsale.order_detail.sku_name} × {postsale.order_detail.sku_count}"
                            )
                            ps_message.append(f"- **退款金额**：{postsale.refund_amount}")
                            
                            if postsale.logistics:
                                postsale.logistics = sorted(
                                    postsale.logistics, key=lambda x: x.create_time, reverse=True
                                )
                                ps_message.append("- **最近物流信息**：")
                                ps_message.append(
                                    f"  - {postsale.logistics[0].logistics_tracking.splitlines()[-1]}"
                                )
                            
                            result.add_response("\n".join(ps_message))
                
        except Exception as e:
            logger.error(f"获取订单详情失败: {e}")
            result.add_response("获取订单详情时出错，请稍后重试。")
        
        return result


class ActionAskReceiveId(Action):
    """
    展示收货地址列表，供选择操作。
    选项包括：现有收货地址、修改并新建收货信息、取消
    """
    
    @property
    def name(self) -> str:
        return "action_ask_receive_id"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import ReceiveInfo, OrderInfo
        
        result = ActionResult()
        user_id = tracker.get_slot("user_id") or "1001"
        order_id = tracker.get_slot("order_id")
        
        slots_to_set = []
        
        try:
            with SessionLocal() as session:
                # 获取用户所有收货信息
                receive_infos = session.query(ReceiveInfo).filter_by(user_id=user_id).all()
                
                # 获取当前订单的收货信息
                current_receive_info = None
                if order_id:
                    order_info = session.query(OrderInfo).filter_by(order_id=order_id).first()
                    if order_info:
                        current_receive_info = order_info.receive
                
                buttons = []
                
                # 遍历收货信息，生成按钮
                for receive_info in receive_infos:
                    buttons.append({
                        "title": f"收货人姓名：{receive_info.receiver_name} - "
                                 f"联系电话：{receive_info.receiver_phone} - "
                                 f"收货地址：{receive_info.receive_province}"
                                 f"{receive_info.receive_city}"
                                 f"{receive_info.receive_district}"
                                 f"{receive_info.receive_street_address}",
                        "payload": f"/SetSlots(receive_id={receive_info.receive_id})",
                    })
                
                # 添加"修改并新建收货信息"和"取消"按钮
                buttons.extend([
                    {
                        "title": "修改并新建收货信息",
                        "payload": "/SetSlots(receive_id=modify)",
                    },
                    {"title": "取消", "payload": "/SetSlots(receive_id=false)"},
                ])
                
                result.add_response("请选择现有的收货信息，或修改并新建收货信息", buttons=buttons)
                
                # 将当前订单的收货信息更新到对应的槽中
                if current_receive_info:
                    tracker.set_slot("receiver_name", current_receive_info.receiver_name)
                    tracker.set_slot("receiver_phone", current_receive_info.receiver_phone)
                    tracker.set_slot("receive_province", current_receive_info.receive_province)
                    tracker.set_slot("receive_city", current_receive_info.receive_city)
                    tracker.set_slot("receive_district", current_receive_info.receive_district)
                    tracker.set_slot("receive_street_address", current_receive_info.receive_street_address)
                    
        except Exception as e:
            logger.error(f"查询地址失败: {e}")
            result.add_response("查询地址时出错，请稍后重试。")
        
        return result


class ActionAskReceiveProvince(Action):
    """询问收货省份"""
    
    @property
    def name(self) -> str:
        return "action_ask_receive_province"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import Region
        
        result = ActionResult()
        
        try:
            with SessionLocal() as session:
                provinces = session.query(Region.province).distinct().all()
            
            buttons = [
                {
                    "title": province[0],
                    "payload": f"/SetSlots(receive_province={province[0]})",
                }
                for province in provinces
            ]
            
            result.add_response("请选择省份", buttons=buttons)
        except Exception as e:
            logger.error(f"查询省份失败: {e}")
            result.add_response("查询省份时出错，请稍后重试。")
        
        return result


class ActionAskReceiveCity(Action):
    """询问收货城市"""
    
    @property
    def name(self) -> str:
        return "action_ask_receive_city"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import Region
        
        result = ActionResult()
        receive_province = tracker.get_slot("receive_province")
        
        try:
            with SessionLocal() as session:
                cities = (
                    session.query(Region.city)
                    .filter(Region.province == receive_province)
                    .distinct()
                    .all()
                )
            
            buttons = [
                {"title": city[0], "payload": f"/SetSlots(receive_city={city[0]})"}
                for city in cities
            ]
            
            result.add_response("请选择城市", buttons=buttons)
        except Exception as e:
            logger.error(f"查询城市失败: {e}")
            result.add_response("查询城市时出错，请稍后重试。")
        
        return result


class ActionAskReceiveDistrict(Action):
    """询问收货区县"""
    
    @property
    def name(self) -> str:
        return "action_ask_receive_district"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import Region
        
        result = ActionResult()
        receive_city = tracker.get_slot("receive_city")
        
        try:
            with SessionLocal() as session:
                districts = (
                    session.query(Region.district)
                    .filter(Region.city == receive_city)
                    .distinct()
                    .all()
                )
            
            buttons = [
                {
                    "title": district[0],
                    "payload": f"/SetSlots(receive_district={district[0]})",
                }
                for district in districts
            ]
            
            result.add_response("请选择城区", buttons=buttons)
        except Exception as e:
            logger.error(f"查询区县失败: {e}")
            result.add_response("查询区县时出错，请稍后重试。")
        
        return result


class ActionAskSetReceiveInfo(Action):
    """
    设置收货信息。
    - 首次调用时展示收货信息并询问确认
    - 确认后执行修改入库
    """
    
    @property
    def name(self) -> str:
        return "action_ask_set_receive_info"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo, ReceiveInfo
        from uuid import uuid4
        
        result = ActionResult()
        receive_id = tracker.get_slot("receive_id")
        set_receive_info = tracker.get_slot("set_receive_info")
        
        # 根据收货id，获取收货信息
        if receive_id in ("modify", "modified"):
            # 从槽中获取收货信息
            receive_info = ReceiveInfo(
                receive_id="rec" + uuid4().hex[:16],
                user_id=tracker.get_slot("user_id") or "1001",
                receiver_name=tracker.get_slot("receiver_name"),
                receiver_phone=tracker.get_slot("receiver_phone"),
                receive_province=tracker.get_slot("receive_province"),
                receive_city=tracker.get_slot("receive_city"),
                receive_district=tracker.get_slot("receive_district"),
                receive_street_address=tracker.get_slot("receive_street_address"),
            )
        else:
            # 从数据库中查询对应收货信息
            try:
                with SessionLocal() as session:
                    receive_info = (
                        session.query(ReceiveInfo).filter_by(receive_id=receive_id).first()
                    )
                    if not receive_info:
                        result.add_response("未找到收货信息，请重新选择。")
                        return result
            except Exception as e:
                logger.error(f"查询收货信息失败: {e}")
                result.add_response("查询收货信息时出错，请稍后重试。")
                return result
        
        # 如果确认修改，执行修改
        if set_receive_info:
            order_id = tracker.get_slot("order_id")
            try:
                with SessionLocal() as session:
                    order_info = (
                        session.query(OrderInfo).filter_by(order_id=order_id).first()
                    )
                    
                    if not order_info:
                        result.add_response("未找到订单，请重新操作。")
                        return result
                    
                    # 如果是新建收货信息
                    if receive_id in ("modify", "modified"):
                        # 检查收货信息是否已存在
                        old_receive_info = (
                            session.query(ReceiveInfo)
                            .filter(
                                ReceiveInfo.user_id == receive_info.user_id,
                                ReceiveInfo.receiver_name == receive_info.receiver_name,
                                ReceiveInfo.receiver_phone == receive_info.receiver_phone,
                                ReceiveInfo.receive_province == receive_info.receive_province,
                                ReceiveInfo.receive_city == receive_info.receive_city,
                                ReceiveInfo.receive_district == receive_info.receive_district,
                                ReceiveInfo.receive_street_address == receive_info.receive_street_address,
                            )
                            .first()
                        )
                        
                        if old_receive_info:
                            receive_info = old_receive_info
                            result.add_response("此收货信息已存在，将不再重复添加")
                        else:
                            session.add(receive_info)
                            session.flush()
                    
                    # 更新订单的收货信息
                    order_info.receive_id = receive_info.receive_id
                    session.commit()
                
                result.add_response("订单收货信息已修改")
                logger.info(f"订单 {order_id} 收货信息更新为: {receive_info.receive_id}")
                
            except Exception as e:
                logger.error(f"修改收货信息失败: {e}")
                result.add_response("修改失败，请稍后重试。")
        else:
            # 初次执行，展示收货信息，询问是否确认修改
            message = [
                f"- 收货人姓名：{receive_info.receiver_name}",
                f"- 联系电话：{receive_info.receiver_phone}",
                f"- 收货省份：{receive_info.receive_province}",
                f"- 收货城市：{receive_info.receive_city}",
                f"- 收货城区：{receive_info.receive_district}",
                f"- 收货地址：{receive_info.receive_street_address}",
            ]
            result.add_response("\n".join(message))
            
            # 发送确认按钮
            result.add_response(
                "是否确认修改？",
                buttons=[
                    {"title": "确认", "payload": "/SetSlots(set_receive_info=true)"},
                    {"title": "取消", "payload": "/SetSlots(set_receive_info=false)"},
                ],
            )
        
        return result


class ActionCancelOrder(Action):
    """取消订单"""
    
    @property
    def name(self) -> str:
        return "action_cancel_order"
    
    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo
        
        result = ActionResult()
        order_id = tracker.get_slot("order_id")
        
        if not order_id:
            result.add_response("订单信息丢失，请重新操作。")
            return result
        
        try:
            with SessionLocal() as session:
                order_info = session.query(OrderInfo).filter_by(order_id=order_id).first()
                
                if not order_info:
                    result.add_response("未找到该订单，请检查订单号是否正确。")
                    return result
                
                # 获取当前订单状态
                old_order_status = order_info.order_status
                
                # 更新订单状态为已取消
                order_info.order_status = "已取消"
                order_info.complete_time = datetime.now()
                session.commit()
            
            # 生成回复消息
            message = "订单已取消"
            # 如果订单状态为待发货，则添加退款金额提示
            if old_order_status == "待发货":
                message += "，退款金额将在24小时内返还您的账户"
            
            result.add_response(message)
            logger.info(f"订单 {order_id} 已取消，原状态: {old_order_status}")

        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            result.add_response("取消失败，请稍后重试。")

        return result


class ActionUrgeShipping(Action):
    """
    催发货 Action

    对待发货订单发送催促通知。
    """

    @property
    def name(self) -> str:
        return "action_urge_shipping"

    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo

        result = ActionResult()
        order_id = tracker.get_slot("order_id")

        if not order_id:
            result.add_response("订单信息丢失，请重新操作。")
            return result

        try:
            with SessionLocal() as session:
                order_info = session.query(OrderInfo).filter_by(order_id=order_id).first()

                if not order_info:
                    result.add_response("未找到该订单，请检查订单号是否正确。")
                    return result

                # 检查订单状态
                if order_info.order_status != "待发货":
                    result.add_response(f"该订单状态为[{order_info.order_status}]，只有待发货订单才能催发货。")
                    return result

                # 模拟催发货操作（实际项目中会发送通知给商家）
                # 这里只是记录催发货请求
                message = [
                    f"✅ 催发货请求已提交",
                    f"",
                    f"订单ID：{order_id}",
                    f"我们会尽快通知商家发货，请耐心等待。",
                    f"",
                    f"如需进一步帮助，请联系人工客服。",
                ]
                result.add_response("\n".join(message))
                logger.info(f"催发货请求已提交: {order_id}")

        except Exception as e:
            logger.error(f"催发货失败: {e}")
            result.add_response("催发货请求提交失败，请稍后重试。")

        return result


class ActionConfirmReceipt(Action):
    """
    确认收货 Action

    对已发货订单确认收货。
    """

    @property
    def name(self) -> str:
        return "action_confirm_receipt"

    async def run(
        self,
        tracker: Any,
        domain: Optional[Any] = None,
        **kwargs: Any,
    ) -> ActionResult:
        from actions.db import SessionLocal
        from actions.db_table_class import OrderInfo

        result = ActionResult()
        order_id = tracker.get_slot("order_id")

        if not order_id:
            result.add_response("订单信息丢失，请重新操作。")
            return result

        try:
            with SessionLocal() as session:
                order_info = session.query(OrderInfo).filter_by(order_id=order_id).first()

                if not order_info:
                    result.add_response("未找到该订单，请检查订单号是否正确。")
                    return result

                # 检查订单状态
                if order_info.order_status != "已发货":
                    result.add_response(f"该订单状态为[{order_info.order_status}]，只有已发货订单才能确认收货。")
                    return result

                # 更新订单状态为已签收
                order_info.order_status = "已签收"
                order_info.delivered_time = datetime.now()
                session.commit()

                message = [
                    f"✅ 已确认收货",
                    f"",
                    f"订单ID：{order_id}",
                    f"感谢您的购买！如有问题，可在15天内申请售后。",
                    f"",
                    f"期待您的评价！",
                ]
                result.add_response("\n".join(message))
                logger.info(f"订单 {order_id} 已确认收货")

        except Exception as e:
            logger.error(f"确认收货失败: {e}")
            result.add_response("确认收货失败，请稍后重试。")

        return result
