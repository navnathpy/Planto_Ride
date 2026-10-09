import React,{useEffect,useState} from 'react';
import {AppState,Linking,Pressable,StyleSheet,Text,View} from 'react-native';
import {ApiClient,formatDate,formatMetric,formatRupees,OverallImpact,PersonalImpact} from './features';

function Card({children}:{children:React.ReactNode}){return <View style={s.card}>{children}</View>;}
function Stat({label,value,note}:{label:string;value:string;note?:string}){return <View style={s.stat}><Text style={s.label}>{label}</Text><Text style={s.value}>{value}</Text>{note?<Text style={s.small}>{note}</Text>:null}</View>;}
export default function ImpactPanel({api,signedIn,onSignIn}:{api:ApiClient;signedIn:boolean;onSignIn:()=>void}){
 const [overall,setOverall]=useState<OverallImpact|null>(null),[personal,setPersonal]=useState<PersonalImpact|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
 const [refresh,setRefresh]=useState(0);
 useEffect(()=>{
  let mounted=true,inFlight=false;setPersonal(null);
  async function load(){
   if(inFlight)return;inFlight=true;
   const results=await Promise.allSettled([api.request<OverallImpact>('/v1/impact/overall'),...(signedIn?[api.request<PersonalImpact>('/v1/impact/me')]:[])]);
   if(mounted){
    const global=results[0];if(global.status==='fulfilled')setOverall(global.value as OverallImpact);
    const own=results[1];if(own?.status==='fulfilled')setPersonal(own.value as PersonalImpact);
    const failed=results.find(r=>r.status==='rejected');setError(failed?.status==='rejected'?(failed.reason instanceof Error?failed.reason.message:'Impact data is unavailable.'):'');setLoading(false);
   }
   inFlight=false;
  }
  void load();const timer=setInterval(()=>{if(AppState.currentState==='active')void load();},30000);
  const sub=AppState.addEventListener('change',state=>{if(state==='active')void load();});
  return()=>{mounted=false;clearInterval(timer);sub.remove();};
 },[api,signedIn,refresh]);
 const heat=overall?.heat;
 const methodology=overall?.methodology||personal?.methodology;
 const carbonSource=methodology?.carbon_source&&/^https:\/\//i.test(methodology.carbon_source)?methodology.carbon_source:null;
 const reference=heat?.reference&&/^https:\/\//i.test(heat.reference)?heat.reference:null;
 return <>
  <Text style={s.eyebrow}>SMALL JOURNEYS. SHARED PROGRESS.</Text><Text style={s.title}>Your impact, with evidence.</Text>
  <Text style={s.copy}>Estimates update as eligible shared rides record distance. Tree funding is shown only after an allocation is recorded.</Text>
  <Pressable accessibilityRole="button" onPress={()=>{setLoading(true);setRefresh(n=>n+1);}} style={s.button}><Text style={s.buttonText}>{loading?'Updating…':'Refresh impact'}</Text></Pressable>
  {error?<Text accessibilityRole="alert" style={s.notice}>{error} Previously loaded values may be out of date.</Text>:null}
  {!signedIn&&<Card><Text style={s.heading}>Your journey starts here</Text><Text>Sign in to see your live and lifetime estimates and your share of recorded tree funding.</Text><Pressable accessibilityRole="button" onPress={onSignIn} style={s.button}><Text style={s.buttonText}>Sign in for my impact</Text></Pressable></Card>}
  {personal&&<>
   <Card><Text style={s.heading}>This ride, right now</Text><Stat label="Estimated CO₂ avoided" value={formatMetric(personal.live.co2_kg,'kg')}/><Text style={s.small}>{formatMetric(personal.live.tracked_km,'km')} of eligible shared travel recorded. Live estimates are provisional and can change. Location sharing must be active.</Text></Card>
   <Card><Text style={s.heading}>Your accumulated impact</Text><Text style={s.small}>Account started {formatDate(personal.since)}. Completed eligible journeys only.</Text><Stat label="Estimated CO₂ avoided" value={formatMetric(personal.lifetime.co2_kg,'kg')}/><Stat label="Estimated vehicle-hours avoided" value={formatMetric(personal.lifetime.vehicle_hours,'hours')} note="Modelled solo-car driving avoided; this is not measured time saved in traffic."/><Text style={s.small}>{personal.lifetime.measured_eligible_bookings} of {personal.lifetime.eligible_bookings} eligible bookings have measured segments · {formatMetric(personal.lifetime.tracked_km,'km')} recorded</Text></Card>
   <Card><Text style={s.heading}>Your contribution to tree funding</Text><Stat label="Attributed to you as a rider" value={formatRupees(personal.contributions.rider_inr)}/><Stat label="Attributed to you as a car owner" value={formatRupees(personal.contributions.owner_inr)}/><Stat label="Your total recorded attribution" value={formatRupees(personal.contributions.total_inr)}/><Text style={s.small}>These are shares of recorded Green Fund allocations, not a percentage of your fare or a personal donation. The pledge is 50% of annual net profit after tax.</Text></Card>
  </>}
  {overall&&<>
   <Card><Text style={s.eyebrow}>TOGETHER, ACROSS PLANTO-RIDE</Text><Text style={s.heading}>Completed journey estimates</Text><Stat label="Estimated CO₂ avoided" value={formatMetric(overall.completed.measurement_available?overall.completed.co2_kg:null,'kg')}/><Stat label="Estimated vehicle-hours avoided" value={formatMetric(overall.completed.measurement_available?overall.completed.vehicle_hours:null,'hours')} note="Not measured congestion reduction or commuter time saved. These vehicle-hours describe driving that the model assumes was avoided."/><Text style={s.small}>{overall.completed.measured_eligible_bookings} of {overall.completed.eligible_bookings} eligible bookings have measured segments · {formatMetric(overall.completed.tracked_km,'km')} recorded</Text><Stat label="Recorded tree fund allocation" value={formatRupees(overall.trees.allocated_inr)}/><Stat label="Trees recorded" value={formatMetric(overall.trees.trees_recorded,'trees')}/><Text style={s.small}>Updated {formatDate(overall.updated_at)}. Figures refresh every 30 seconds while this tab is open.</Text></Card>
   <Card><Text style={s.heading}>Urban cooling</Text><Stat label="Measured temperature reduction" value={heat?.reduction_c===null||heat?.reduction_c===undefined?'Not measured':formatMetric(heat.reduction_c,'°C')}/><Text style={s.copy}>{heat?.reduction_c===null||heat?.reduction_c===undefined?'Ride savings cannot be converted directly into a city temperature reduction. A local temperature study is needed before a cooling result can be shown.':'This result applies only to the study area and method stated below; it is not a city-wide effect or a temperature saving for each trip.'}</Text>{heat?.scope?<Text style={s.small}>Study scope: {heat.scope}</Text>:null}{heat?.measured_at?<Text style={s.small}>Measured: {formatDate(heat.measured_at)}</Text>:null}{heat?.reference?<Text selectable style={s.small}>Evidence: {heat.reference}</Text>:null}{reference?<Pressable accessibilityRole="link" onPress={()=>void Linking.openURL(reference).catch(()=>setError('Could not open the study link.'))}><Text style={s.link}>Open study evidence</Text></Pressable>:null}</Card>
  </>}
  <Card><Text style={s.heading}>How the estimates work</Text><Text style={s.copy}>A shared trip counts only when the car owner was already making the journey and the rider says they would otherwise have driven alone. Car and Bike bookings do not automatically earn savings.</Text><Text style={s.copy}>Recorded distance uses accepted GPS samples, so missing or poor location data can leave gaps. The current model uses a 0.249 kg CO₂/km US petrol-car proxy. It is not a measurement of your particular vehicle or a certified carbon credit.</Text><Text style={s.small}>Carbon and vehicle-hour figures are estimates, not verified environmental outcomes. Tree funding and cooling measurements are tracked separately.</Text>{methodology?.coverage?<Text style={s.small}>{methodology.coverage}</Text>:null}{methodology?.attribution?<Text style={s.small}>{methodology.attribution}</Text>:null}{carbonSource?<Pressable accessibilityRole="link" onPress={()=>void Linking.openURL(carbonSource).catch(()=>setError('Could not open the methodology source.'))}><Text style={s.link}>View carbon estimate source</Text></Pressable>:null}</Card>
 </>;
}
const s=StyleSheet.create({title:{fontSize:34,fontWeight:'800',color:'#123d2d',lineHeight:39},eyebrow:{fontSize:11,fontWeight:'800',letterSpacing:1.5,color:'#557546'},heading:{fontSize:21,fontWeight:'700',color:'#123d2d'},card:{backgroundColor:'white',borderRadius:20,padding:20,gap:14,borderWidth:1,borderColor:'#dfe5d9'},stat:{gap:4,paddingVertical:5},label:{fontSize:14,fontWeight:'600',color:'#385242'},value:{fontSize:27,fontWeight:'800',color:'#123d2d'},copy:{fontSize:15,lineHeight:23,color:'#254533'},small:{fontSize:12,lineHeight:18,color:'#59675b'},button:{backgroundColor:'#123d2d',padding:15,borderRadius:12,alignItems:'center'},buttonText:{fontWeight:'700',color:'white',textAlign:'center'},notice:{backgroundColor:'#fff0d5',padding:14,borderRadius:12,color:'#754317',lineHeight:21},link:{fontWeight:'700',color:'#235f3a',textDecorationLine:'underline'}});
