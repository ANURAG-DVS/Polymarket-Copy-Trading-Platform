import { useQuery } from '@tanstack/react-query';
import apiClient from '@/utils/api-client';

interface TopTrade {
    market_id: string;
    market_title: string;
    outcome: string;
    volume_24h: number;
    current_price: number;
    liquidity: number;
    end_date: string;
    created_at: string;
    image_url: string;
    category: string;
}

export const useTopTrades = (hours: number = 24, limit: number = 10) => {
    return useQuery({
        queryKey: ['topTrades', hours, limit],
        queryFn: async () => {
            const response = await apiClient.get<TopTrade[]>(`/trades/top`, {
                params: { hours, limit }
            });
            return response.data;
        },
        refetchInterval: 60000, // Refetch every 60 seconds
        staleTime: 30000, // Consider data stale after 30 seconds
    });
};
