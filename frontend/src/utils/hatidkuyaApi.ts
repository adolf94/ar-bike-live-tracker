import api from './api';

export interface CreateOrderPayload {
  from_address: string;
  to_address: string;
  from_lat?: number;
  from_lng?: number;
  to_lat?: number;
  to_lng?: number;
  recipient_name?: string;
  item_description?: string;
}

export interface OrderLocation {
  lat: number;
  lng: number;
  timestamp?: string;
}

export interface OrderData {
  id: string;
  tracking_id: string;
  from_address: string;
  to_address: string;
  from_coords?: OrderLocation | null;
  to_coords?: OrderLocation | null;
  recipient_name?: string;
  item_description?: string;
  status: 'active' | 'completed' | 'cancelled';
  delivery_stage?: 'going_to_pickup' | 'going_to_dropoff' | 'completed';
  created_at: string;
  last_location?: OrderLocation | null;
}

export interface LocationSearchResult {
  place_id?: string;
  name: string;
  display_name: string;
  lat: number;
  lon: number;
}

export interface SignalRNegotiation {
  url: string;
  accessToken: string;
}

export const hatidkuyaApi = {
  async createOrder(
    fromAddress: string,
    toAddress: string,
    recipientName?: string,
    itemDescription?: string,
    fromCoords?: { lat: number; lng: number },
    toCoords?: { lat: number; lng: number }
  ): Promise<any> {
    const res = await api.post('/api/orders', {
      from_address: fromAddress,
      to_address: toAddress,
      from_lat: fromCoords?.lat,
      from_lng: fromCoords?.lng,
      to_lat: toCoords?.lat,
      to_lng: toCoords?.lng,
      recipient_name: recipientName,
      item_description: itemDescription,
    });
    return res.data;
  },

  async getOrder(trackingId: string): Promise<OrderData> {
    const res = await api.get(`/api/orders/${trackingId}`);
    return res.data;
  },

  async getActiveOrder(): Promise<OrderData | null> {
    const res = await api.get('/api/orders/active');
    return res.data;
  },

  async updateLocation(orderIdOrLat: string | number, maybeLat?: number, maybeLng?: number): Promise<OrderData> {
    let lat: number;
    let lng: number;
    if (typeof orderIdOrLat === 'number') {
      lat = orderIdOrLat;
      lng = maybeLat!;
    } else {
      lat = maybeLat!;
      lng = maybeLng!;
    }
    const res = await api.post('/api/orders/location', {
      lat,
      lng,
    });
    return res.data;
  },

  async updateDeliveryStage(orderId: string, stage: 'going_to_pickup' | 'going_to_dropoff' | 'completed'): Promise<OrderData> {
    const res = await api.post(`/api/orders/${orderId}/stage`, {
      stage,
    });
    return res.data;
  },

  async completeOrder(orderId: string): Promise<OrderData> {
    const res = await api.post(`/api/orders/${orderId}/complete`);
    return res.data;
  },

  async negotiate(trackingId: string): Promise<SignalRNegotiation> {
    const res = await api.post(`/api/negotiate/${trackingId}`);
    return res.data;
  },

  async joinGroup(trackingId: string, connectionId: string): Promise<void> {
    await api.post(`/api/join/${trackingId}`, { connectionId });
  },

  async searchLocations(query: string): Promise<LocationSearchResult[]> {
    const res = await api.get('/api/locations/search', {
      params: { q: query },
    });
    return res.data;
  },

  async getOrderLocationHistory(trackingId: string): Promise<Array<{ lat: number; lng: number; timestamp: string }>> {
    const res = await api.get(`/api/orders/${trackingId}/history`);
    return res.data;
  },

  async getLocationDetails(placeId?: string, address?: string): Promise<{ lat: number; lng: number; address: string }> {
    const res = await api.get('/api/locations/details', {
      params: { place_id: placeId, address },
    });
    return res.data;
  },
};
