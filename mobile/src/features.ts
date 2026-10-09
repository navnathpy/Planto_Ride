import type {createApi} from './api';

export type ApiClient=ReturnType<typeof createApi>;
export type CaptainAction='all_good'|'need_help'|'unsafe'|'status';
export type CaptainCheckin={id:string;status:'awaiting'|'all_good'|'needs_help'|'unsafe';due_at:number};
export type CaptainConversation={
 captain:{id:string;name:string;automated:true;booking_id:string};
 messages:{id:string;role:'captain'|'rider';text:string;created:number}[];
 checkin:CaptainCheckin|null;next_checkin_at:number|null;trip_status:string;
 delivery:'foreground';concern_reported:boolean;
};
export type PendingCheckin={booking_id:string;captain_id:string;checkin_id:string;due_at:number;status:'awaiting'};
export type ImpactTotals={co2_kg:number|null;vehicle_hours:number|null;tracked_km:number;eligible_bookings:number;measured_eligible_bookings:number;tracked_bookings:number;bookings:number;measurement_available:boolean};
export type ImpactMethodology={co2_kg_per_km:number;carbon_source:string;heat_source:string;carbon_basis:string;eligibility:string;traffic_basis:string;coverage:string;attribution:string;trees_basis:string;heat_basis:string};
export type PersonalImpact={since:number|string;live:ImpactTotals;lifetime:ImpactTotals;attribution:{rider:ImpactTotals;owner_enabled:ImpactTotals};contributions:{rider_inr:number;owner_inr:number;total_inr:number};methodology:ImpactMethodology};
export type OverallImpact={completed:ImpactTotals;trees:{allocated_inr:number;trees_recorded:number;evidence_records:number};heat:{reduction_c:number|null;scope?:string;reference?:string|null;measured_at?:number|string|null;citywide_reduction_c:null};updated_at:number|string;methodology:ImpactMethodology};

export function formatMetric(value:number|null|undefined,unit:string){
 return typeof value==='number'&&Number.isFinite(value)?`${value.toLocaleString('en-IN',{maximumFractionDigits:2})} ${unit}`:'Not enough data';
}
export function formatRupees(value:number|null|undefined){
 return typeof value==='number'&&Number.isFinite(value)?`₹${value.toLocaleString('en-IN',{maximumFractionDigits:2})}`:'Not available';
}
export function formatDate(value:number|string|null|undefined){
 if(value===null||value===undefined)return 'Not available';
 const d=new Date(typeof value==='number'&&value<1e12?value*1000:value);
 return Number.isNaN(d.getTime())?'Not available':d.toLocaleString('en-IN');
}
// This UUID deduplicates chat submissions; it is not an authentication token.
export function messageRequestId(){
 return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{
  const r=Math.floor(Math.random()*16);return (c==='x'?r:(r&3)|8).toString(16);
 });
}
