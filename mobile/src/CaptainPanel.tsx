import React,{useEffect,useRef,useState} from 'react';
import {AppState,Modal,Pressable,ScrollView,StyleSheet,Text,TextInput,View} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {ApiClient,CaptainAction,CaptainConversation,formatDate,messageRequestId} from './features';

export default function CaptainPanel({bookingId,api,onClose,onSos,onUpdated}:{bookingId:string;api:ApiClient;onClose:()=>void;onSos:()=>void;onUpdated:()=>void}){
 const [chat,setChat]=useState<CaptainConversation|null>(null),[draft,setDraft]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const attempt=useRef<{signature:string;id:string}|null>(null),sending=useRef(false),latest=useRef(0);
 useEffect(()=>{
  let mounted=true;
  async function refresh(){
   if(sending.current)return;const request=++latest.current;
   try{const value=await api.request<CaptainConversation>(`/v1/bookings/${bookingId}/captain`);if(mounted&&request===latest.current){setChat(value);setError('');}}
   catch(e){if(mounted&&request===latest.current)setError(e instanceof Error?e.message:'Captain is unavailable.');}
  }
  void refresh();const timer=setInterval(()=>{if(AppState.currentState==='active')void refresh();},30000);
  const sub=AppState.addEventListener('change',state=>{if(state==='active')void refresh();});
  return()=>{mounted=false;++latest.current;clearInterval(timer);sub.remove();};
 },[bookingId,api]);
 async function send(text:string,action?:CaptainAction){
  if(sending.current||!text.trim())return;
  const checkin=chat?.checkin?.status==='awaiting'?chat.checkin.id:undefined;
  const body={text:text.trim(),...(action?{action}:{}),...(action&&action!=='status'&&checkin?{checkin_id:checkin}:{})};
  const signature=JSON.stringify(body);
  if(attempt.current?.signature!==signature)attempt.current={signature,id:messageRequestId()};
  sending.current=true;const request=++latest.current;setBusy(true);setError('');
  try{const next=await api.request<CaptainConversation>(`/v1/bookings/${bookingId}/captain/messages`,'POST',{...body,request_id:attempt.current.id});if(request===latest.current){setChat(next);setDraft('');attempt.current=null;onUpdated();}}
  catch(e){if(request===latest.current)setError(e instanceof Error?e.message:'Message could not be sent. Try again.');}
  finally{sending.current=false;if(request===latest.current)setBusy(false);}
 }
 const button=(label:string,action:()=>void,danger=false,disabled=busy)=><Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={action} style={[s.button,danger&&s.danger,disabled&&{opacity:.5}]}><Text style={s.buttonText}>{label}</Text></Pressable>;
 const ended=!!chat&&['completed','cancelled'].includes(chat.trip_status);
 return <Modal visible animationType="slide" onRequestClose={onClose}><SafeAreaView style={s.screen}>
  <View style={s.header}><View style={{flex:1}}><Text style={s.heading}>{chat?.captain.name||'Your Captain'}</Text><Text style={s.small}>Automated ride companion</Text></View>{button('Close',onClose,false,false)}</View>
  <View style={{paddingHorizontal:18,paddingTop:8}}>{button('SOS emergency help',onSos,true,false)}</View>
  <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
   <Text style={s.notice}>Captain is a chatbot, not your driver or a monitored emergency service. It checks in while the app is open. It cannot confirm that you are safe or dispatch help.</Text>
   {error?<Text accessibilityRole="alert" style={s.error}>{error}</Text>:null}
   {!chat&&!error&&<Text>Connecting to your ride’s Captain…</Text>}
   {chat?.messages.map(m=><View key={m.id} style={[s.message,m.role==='rider'&&s.rider]}><Text style={s.label}>{m.role==='captain'?chat.captain.name:'You'}</Text><Text selectable style={s.messageText}>{m.text}</Text><Text style={s.small}>{formatDate(m.created)}</Text></View>)}
   {chat?.checkin?.status==='awaiting'&&<Text accessibilityLiveRegion="polite" style={s.notice}>Captain is checking in: is your ride going well?</Text>}
   {chat?.concern_reported&&<Text style={s.notice}>A concern is recorded for operator review. For urgent help, open SOS and choose a call or share action.</Text>}
   {chat&&<><View style={s.row}>{!ended&&button('All good',()=>void send('My ride is going well.','all_good'),false,busy||chat.checkin?.status!=='awaiting')}{!ended&&button('I need help',()=>void send('I need help with my ride.','need_help'))}{!ended&&button('I feel unsafe',()=>void send('I feel unsafe.','unsafe'),true)}{button('Ride status',()=>void send('What is my ride status?','status'))}</View>
    <Text style={s.small}>{ended?'This ride has ended. You can view its Captain conversation and ask for its status.':'Check-ins stop when the app is in the background. Keep SOS available for immediate concerns.'}</Text>
    <Text style={s.label}>Message Captain</Text><TextInput accessibilityLabel="Message Captain" multiline maxLength={1000} value={draft} onChangeText={setDraft} style={s.input} placeholder="Ask about your ride or share a concern"/>
    {button(busy?'Sending…':'Send message',()=>void send(draft),false,busy||!draft.trim())}
   </>}
  </ScrollView>
 </SafeAreaView></Modal>;
}
const s=StyleSheet.create({screen:{flex:1,backgroundColor:'#f6f7f1'},header:{padding:18,flexDirection:'row',alignItems:'center',gap:12,backgroundColor:'white'},heading:{fontSize:23,fontWeight:'800',color:'#123d2d'},content:{padding:20,gap:14,paddingBottom:40,maxWidth:760,width:'100%',alignSelf:'center'},small:{fontSize:12,lineHeight:18,color:'#59675b'},notice:{backgroundColor:'#edf3df',borderRadius:12,padding:14,lineHeight:21,color:'#244b31'},error:{backgroundColor:'#fff0d5',padding:14,borderRadius:12,color:'#754317'},message:{alignSelf:'flex-start',maxWidth:'94%',backgroundColor:'white',borderRadius:15,padding:15,gap:6,borderWidth:1,borderColor:'#dfe5d9'},rider:{alignSelf:'flex-end',backgroundColor:'#e2ecd5'},messageText:{fontSize:16,lineHeight:23,color:'#163e2b'},label:{fontWeight:'700',color:'#123d2d'},row:{flexDirection:'row',flexWrap:'wrap',gap:8},button:{backgroundColor:'#123d2d',padding:13,borderRadius:12,alignItems:'center'},buttonText:{fontWeight:'700',color:'white'},danger:{backgroundColor:'#b12737'},input:{backgroundColor:'white',borderColor:'#cdd8c9',borderWidth:1,borderRadius:10,padding:13,fontSize:16,color:'#153b28',minHeight:90,textAlignVertical:'top'}});
