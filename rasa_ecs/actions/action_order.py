from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, ActionExecutionRejected
from rasa_sdk.executor import CollectingDispatcher

from uuid import uuid4
from .db import SessionLocal
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from .db_table_class import OrderInfo, Postsale, OrderStatus, ReceiveInfo, Region

class AskOrderId(Action):
    """选择一个订单"""

    def name(self) -> str:
        return "action_ask_order_id"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        events = []
        with SessionLocal() as session:
            order_infos = (
                session.query(OrderInfo)
                .join(OrderInfo.order_status_)  # 关联订单状态表
                .options(joinedload(OrderInfo.order_detail))  # 预加载 order_detail
                .filter(self.get_query_condition(tracker))
                .all()
            )
        order_nums = len(order_infos)
        if order_nums == 1:
            # 如果只有一个订单，询问是否查询此订单
            order_info = order_infos[0]
            message = [
                "查找到一个订单",
                f"[{order_info.order_status}]**订单ID**：{order_info.order_id}",
            ]
            for order_detail in order_info.order_detail:
                message.append(f"- {order_detail.sku_name} × {order_detail.sku_count}")
            dispatcher.utter_message(
                text="\n".join(message),
                buttons=[
                    {
                        "title": "确认",
                        "payload": f"/SetSlots(order_id={order_info.order_id})",
                    },
                    {"title": "返回", "payload": "/SetSlots(order_id=false)"},
                ],
            )
        elif order_nums > 1:
            # 如果有多个订单，用户选择其中一个
            buttons = [
                {
                    "title": "\n".join(
                        [
                            f"[{order_info.order_status}]订单ID：{order_info.order_id}",
                        ]
                        + [
                            f"- {order_detail.sku_name} × {order_detail.sku_count}"
                            for order_detail in order_info.order_detail
                        ]
                    ),
                    "payload": f"/SetSlots(order_id={order_info.order_id})",
                }
                for order_info in order_infos
            ]
            buttons.append({"title": "返回", "payload": "/SetSlots(order_id=false)"})
            dispatcher.utter_message(text="请选择订单", buttons=buttons)
        else:
            # 没有订单
            dispatcher.utter_message(text="暂无订单")
            events.append(SlotSet("order_id", "false"))
            # 打断action_listen动作
            events.append(ActionExecutionRejected("action_listen"))
        return events

    def get_query_condition(self, tracker: Tracker):
        """获取查询条件"""
        user_id = tracker.get_slot("user_id")
        goto = tracker.get_slot("goto")
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
            
class GetOrderDetail(Action):
    """获取订单详情"""

    def name(self) -> str:
        return "action_get_order_detail"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]
    ) -> List[Dict[Text, Any]]:
        order_id = tracker.get_slot("order_id")
        # 查询订单
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
        # 拼接订单信息
        message = [f"- [{order_info.order_status}]**订单ID**：{order_info.order_id}"]
        for k, v in {
            "创建时间": order_info.create_time,
            "支付时间": order_info.payment_time,
            "签收时间": order_info.delivered_time,
            "完成时间": order_info.complete_time,
        }.items():
            if v:
                message.append(f"  - {k}：{v}")
        # 拼接订单明细信息
        message.append("- **订单明细**：")
        total_total_amount = 0.0
        total_discount_amount = 0.0
        total_final_amount = 0.0
        for order_detail in order_info.order_detail:
            message.append(
                f"  - {order_detail.sku_name} × {order_detail.sku_count} | \
                {order_detail.total_amount}-{order_detail.discount_amount}={order_detail.final_amount}"
            )
            total_total_amount += float(order_detail.total_amount)
            total_discount_amount += float(order_detail.discount_amount)
            total_final_amount += float(order_detail.final_amount)
        message.append(
            f"  - **合计**：{total_total_amount}-{total_discount_amount}={total_final_amount}"
        )
        # 拼接收货信息
        message.extend(
            [
                "- **收货信息**：",
                f"  - 收货人：{order_info.receive.receiver_name}",
                f"  - 联系电话：{order_info.receive.receiver_phone}",
                f"  - 收货地址：{order_info.receive.receive_province}\
                {order_info.receive.receive_city}\
                {order_info.receive.receive_district}\
                {order_info.receive.receive_street_address}",
            ]
        )
        # 拼接最近物流信息
        logistics = order_info.logistics
        if logistics:
            message.append("- **最近物流信息**：")
            message.append(f"  - {logistics[0].logistics_tracking.splitlines()[-1]}")
        dispatcher.utter_message(text="\n".join(message))
        if order_info.order_status_.status_code < 400:
            return []
        # 打印售后信息
        # 获取所有订单明细ID
        order_detail_ids = [
            order_detail.order_detail_id for order_detail in order_info.order_detail
        ]
        # 查询每个订单明细最新的售后信息
        with SessionLocal() as session:
            # 子查询：postsale 按 order_detail_id 分组，取最大的 postsale.create_time
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
                    (Postsale.order_detail_id == subquery.c.order_detail_id)
                    & (Postsale.create_time == subquery.c.max_time),
                )
                .options(joinedload(Postsale.order_detail))
                .options(joinedload(Postsale.logistics))
                .all()
            )
        if not postsales:
            return []
        # 拼接售后信息
        for postsale in postsales:
            message = [
                f"- [{postsale.postsale_status}]**售后ID**：{postsale.postsale_id}"
            ]
            message.append("- **订单明细**：")
            message.append(
                f"  -{postsale.order_detail.sku_name} × {postsale.order_detail.sku_count}"
            )
            message.append(f"- **退款金额**：{postsale.refund_amount}")
            # 获取最新的物流信息
            if postsale.logistics:
                postsale.logistics = sorted(
                    postsale.logistics, key=lambda x: x.create_time, reverse=True
                )
                message.append("- **最近物流信息**：")
                message.append(
                    f"  - {postsale.logistics[0].logistics_tracking.splitlines()[-1]}"
                )
            dispatcher.utter_message(text="\n".join(message))
        return []