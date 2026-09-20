"use client";

import { DeleteOutlined, EditOutlined, PlusOutlined, StarOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Form, Input, Modal, Space, Tag, Typography, message } from "antd";
import { useCallback, useEffect, useState } from "react";
import StorefrontLayout from "@/components/StorefrontLayout";
import { createCustomerAddress, deleteCustomerAddress, fetchCustomerAddresses, getCustomerEmail, setDefaultCustomerAddress, updateCustomerAddress, type CustomerAddress } from "@/services/saleor";

export default function AddressesPage() {
  const [addresses, setAddresses] = useState<CustomerAddress[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<CustomerAddress | null>(null);
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const reload = useCallback(() => fetchCustomerAddresses().then(setAddresses).finally(() => setLoading(false)), []);
  useEffect(() => { if (getCustomerEmail()) reload(); else setLoading(false); }, [reload]);

  async function submit(values: Record<string, string>) {
    setBusy(true);
    try {
      const input = { ...values, country: values.country || "US" };
      if (editing) await updateCustomerAddress(editing.id, input); else await createCustomerAddress(input);
      messageApi.success("地址已保存");
      setOpen(false);
      form.resetFields();
      setEditing(null);
      await reload();
    } catch (error) {
      messageApi.error(String(error));
    } finally {
      setBusy(false);
    }
  }

  function edit(address: CustomerAddress) {
    setEditing(address);
    form.setFieldsValue({ ...address, country: address.country.code });
    setOpen(true);
  }

  async function makeDefault(id: string) {
    try { await setDefaultCustomerAddress(id); messageApi.success("默认地址已更新"); await reload(); }
    catch (error) { messageApi.error(String(error)); }
  }

  async function remove(id: string) {
    try { await deleteCustomerAddress(id); messageApi.success("地址已删除"); await reload(); }
    catch (error) { messageApi.error(String(error)); }
  }

  if (!getCustomerEmail()) return <StorefrontLayout><Empty description="登录后管理收货地址"><Button type="primary" onClick={() => window.dispatchEvent(new Event("sf-open-auth"))}>登录 / 注册</Button></Empty></StorefrontLayout>;

  return (
    <StorefrontLayout>
      {contextHolder}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div><Typography.Title level={3} style={{ margin: 0 }}>收货地址</Typography.Title><Typography.Text type="secondary">地址会保存到 Saleor 账户</Typography.Text></div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); form.resetFields(); setOpen(true); }}>新增地址</Button>
      </div>
      {loading ? <Card loading /> : addresses.length === 0 ? <Empty description="还没有保存地址" /> : addresses.map((address) => (
        <Card key={address.id} style={{ marginBottom: 12 }}>
          <Space direction="vertical" size={4} style={{ width: "100%" }}>
            <Space><Typography.Text strong>{address.firstName} {address.lastName}</Typography.Text>{address.isDefaultShippingAddress && <Tag color="blue">默认收货地址</Tag>}</Space>
            <Typography.Text>{address.streetAddress1}{address.streetAddress2 ? `，${address.streetAddress2}` : ""}</Typography.Text>
            <Typography.Text type="secondary">{address.city} {address.countryArea} {address.postalCode} · {address.country.code} · {address.phone}</Typography.Text>
            <Space>
              {!address.isDefaultShippingAddress && <Button type="link" icon={<StarOutlined />} onClick={() => makeDefault(address.id)}>设为默认</Button>}
              <Button type="link" icon={<EditOutlined />} onClick={() => edit(address)}>编辑</Button>
              <Button danger type="link" icon={<DeleteOutlined />} onClick={() => remove(address.id)}>删除</Button>
            </Space>
          </Space>
        </Card>
      ))}
      <Modal title={editing ? "编辑收货地址" : "新增收货地址"} open={open} onCancel={() => { setOpen(false); setEditing(null); }} onOk={() => form.submit()} confirmLoading={busy} destroyOnClose>
        <Form form={form} layout="vertical" onFinish={submit} initialValues={{ country: "US" }}>
          <Space style={{ width: "100%" }}><Form.Item name="firstName" label="名" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="lastName" label="姓" rules={[{ required: true }]}><Input /></Form.Item></Space>
          <Form.Item name="streetAddress1" label="详细地址" rules={[{ required: true }]}><Input /></Form.Item>
          <Space style={{ width: "100%" }}><Form.Item name="city" label="城市" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="countryArea" label="州 / 省"><Input /></Form.Item><Form.Item name="postalCode" label="邮编" rules={[{ required: true }]}><Input /></Form.Item></Space>
          <Space style={{ width: "100%" }}><Form.Item name="country" label="国家" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="phone" label="电话" rules={[{ required: true }]}><Input /></Form.Item></Space>
        </Form>
      </Modal>
    </StorefrontLayout>
  );
}
